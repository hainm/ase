import os
import sys
import time
import argparse
import traceback

from ase.cli.command import Command
from ase.calculators.calculator import get_calculator, \
    names as calculator_names
import ase.db as db


def str2dict(s, namespace={}, sep='='):
    """Convert comma-separated key=value string to dictionary.

    Examples:

    >>> str2dict('xc=PBE,nbands=200,parallel={band:4}')
    {'xc': 'PBE', 'nbands': 200, 'parallel': {'band': 4}}
    >>> str2dict('a=1.2,b=True,c=ab,d=1,2,3,e={f:42,g:cd}')
    {'a': 1.2, 'c': 'ab', 'b': True, 'e': {'g': 'cd', 'f': 42}, 'd': (1, 2, 3)}
    """
    
    def myeval(value):
        try:
            value = eval(value, namespace)
        except (NameError, SyntaxError):
            pass
        return value

    dct = {}
    s = (s + ',').split(sep)
    for i in range(len(s) - 1):
        key = s[i]
        m = s[i + 1].rfind(',')
        value = s[i + 1][:m]
        if value[0] == '{':
            assert value[-1] == '}'
            value = str2dict(value[1:-1], namespace, ':')
        if value[0] == '(':
            assert value[-1] == ')'
            value = [myeval(t) for t in value[1:-1].split(',')]
        else:
            value = myeval(value)
        dct[key] = value
        s[i + 1] = s[i + 1][m + 1:]
    return dct


class RunCommand(Command):
    db = None

    def add_parser(self, subparser):
        parser = subparser.add_parser('run', help='run ...')
        self.add_arguments(parser)

    def add_arguments(self, parser):
        add = parser.add_argument
        add('--after')
        calculator = self.hook.get('name', 'emt')
        if calculator == 'emt':
            help = ('Name of calculator to use: ' +
                    ', '.join(calculator_names) +
                    '.  Default is emt.')
        else:
            help=argparse.SUPPRESS
        add('-c', '--calculator', default=calculator, help=help)
        add('-p', '--parameters', default='',
            metavar='key=value,...',
            help='Comma-separated key=value pairs of ' +
            'calculator specific parameters.')
        add('-d', '--database',
            help='Use a filename with a ".sqlite" extension for a sqlite3 ' +
            'database or a ".json" extension for a simple json database.  ' +
            'Default is no database')
        add('-l', '--use-lock-file', action='store_true',
            help='Use a lock-file to syncronize access to database.')
        add('-S', '--skip', action='store_true',
            help='Skip calculations already done.')
        add('--properties', default='efsdMm',
            help='Default value is "efsdMm" meaning calculate energy, ' +
            'forces, stress, dipole moment, total magnetic moment and ' +
            'atomic magnetic moments.')
    
    def run(self, atoms, name):
        args = self.args

        if self.db is None:
            # Create database object:
            self.db = db.connect(args.database,
                                 use_lock_file=args.use_lock_file)

        if args.tag:
            id = name + '-' + args.tag
        else:
            id = name

        skip = False
        if args.skip:
            try:
                self.db.write(id, None, replace=False)
            except db.IdCollisionError:
                skip = True
        
        if not skip:
            self.set_calculator(atoms, name)

            tstart = time.time()
            try:
                data = self.calculate(atoms, name)
            except KeyboardInterrupt:
                raise
            except Exception:
                self.log(name, 'FAILED')
                traceback.print_exc(file=self.logfile)
            else:
                tstop = time.time()
                data['time'] = tstop - tstart
                data['ase_cli'] = ' '.join(sys.argv[1:])
                self.db.write(id, atoms, data=data)

    def set_calculator(self, atoms, name):
        args = self.args
        cls = get_calculator(args.calculator)
        parameters = self.get_parameters()
        if getattr(cls, 'nolabel', False):
            atoms.calc = cls(**parameters)
        else:
            atoms.calc = cls(label=self.get_filename(name), **parameters)

    def get_parameters(self):
        namespace = self.hook.get('namespace', {})
        parameters = str2dict(self.args.parameters, namespace)
        return parameters

    def calculate(self, atoms, name):
        args = self.args

        for p in args.properties or 'efsdMm':
            property, method = {'e': ('energy', 'get_potential_energy'),
                                'f': ('forces', 'get_forces'),
                                's': ('stress', 'get_stress'),
                                'd': ('dipole', 'get_dipole_moment'),
                                'M': ('magmom', 'get_magnetic_moment'),
                                'm': ('magmoms', 'get_magnetic_moments')}[p]
            try:
                x = getattr(atoms, method)()
            except NotImplementedError:
                pass

        data = {}
        if args.after:
            exec args.after in {'atoms': atoms, 'data': data}
        
        return data
