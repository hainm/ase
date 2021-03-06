from __future__ import print_function
# Copyright 2008, 2009
# CAMd (see accompanying license files for details).
from __future__ import print_function
import sys
from optparse import OptionParser

from ase.gui.i18n import enable_localization


# Grrr, older versions (pre-python2.7) of optparse have a bug
# which prevents non-ascii descriptions.  How do we circumvent this?
# For now, we'll have to use English in the command line options then.


def build_parser():
    parser = OptionParser(usage='%prog [options] [file[, file2, ...]]',
                          version='%prog 0.1',
                          description='See the online manual ' +
                          '(https://wiki.fysik.dtu.dk/ase/ase/gui/gui.html) ' +
                          'for more information.')
    parser.add_option('-n', '--image-number',
                      default=':', metavar='NUMBER',
                      help='Pick image(s) from trajectory.  NUMBER can be a '
                      'single number (use a negative number to count from '
                      'the back) or a range: start:stop:step, where the '
                      '":step" part can be left out - default values are '
                      '0:nimages:1.')
    parser.add_option('-u', '--show-unit-cell', type='int',
                      default=1, metavar='I',
                      help="0: Don't show unit cell.  1: Show unit cell.  "
                      '2: Show all of unit cell.')
    parser.add_option('-r', '--repeat',
                      default='1',
                      help='Repeat unit cell.  Use "-r 2" or "-r 2,3,1".')
    parser.add_option('-R', '--rotations', default='',
                      help='Examples: "-R -90x", "-R 90z,-30x".')
    parser.add_option('-o', '--output', metavar='FILE',
                      help='Write configurations to FILE.')
    parser.add_option('-g', '--graph',
                      # TRANSLATORS: EXPR abbreviates 'expression'
                      metavar='EXPR',
                      help='Plot x,y1,y2,... graph from configurations or '
                      'write data to sdtout in terminal mode.  Use the '
                      'symbols: i, s, d, fmax, e, ekin, A, R, E and F.  See '
                      'https://wiki.fysik.dtu.dk/ase/ase/gui/gui.html'
                      '#plotting-data for more details.')
    parser.add_option('-t', '--terminal',
                      action='store_true',
                      default=False,
                      help='Run in terminal window - no GUI.')
    parser.add_option('--aneb',
                      action='store_true',
                      default=False,
                      help='Read ANEB data.')
    parser.add_option('--interpolate',
                      type='int', metavar='N',
                      help='Interpolate N images between 2 given images.')
    parser.add_option('-b', '--bonds',
                      action='store_true',
                      default=False,
                      help='Draw bonds between atoms.')
    parser.add_option('-s', '--scale', dest='radii_scale', metavar='FLOAT',
                      default=None, type=float,
                      help='Scale covalent radii.')
    parser.add_option('-v', '--verbose', action='store_true',
                      help='Verbose mode.')
    return parser


def main():
    enable_localization()
    from gettext import gettext as _
    parser = build_parser()
    opt, args = parser.parse_args()

    from ase.gui.images import Images
    from ase.atoms import Atoms

    def run(opt, args):
        images = Images()

        if opt.aneb:
            opt.image_number = '-1'

        if len(args) > 0:
            from ase.io import string2index
            images.read(args, string2index(opt.image_number))
        else:
            images.initialize([Atoms()])

        if opt.interpolate:
            images.interpolate(opt.interpolate)

        if opt.aneb:
            images.aneb()

        if opt.repeat != '1':
            r = opt.repeat.split(',')
            if len(r) == 1:
                r = 3 * r
            images.repeat_images([int(c) for c in r])

        if opt.radii_scale:
            images.set_radii(opt.radii_scale)

        if opt.output is not None:
            images.write(opt.output, rotations=opt.rotations,
                         show_unit_cell=opt.show_unit_cell)
            opt.terminal = True

        if opt.terminal:
            if opt.graph is not None:
                data = images.graph(opt.graph)
                for line in data.T:
                    for x in line:
                        print(x, end=' ')
                    print()
        else:
            from ase.gui.gui import GUI
            import ase.gui.gtkexcepthook
            ase
            gui = GUI(images, opt.rotations, opt.show_unit_cell, opt.bonds)
            gui.run(opt.graph)

    try:
        run(opt, args)
    except KeyboardInterrupt:
        pass
    except Exception as x:
        if opt.verbose:
            raise
        else:
            print('{0}: {1}'.format(x.__class__.__name__, x), file=sys.stderr)
            print(_('To get a full traceback, use: ase-gui --verbose'),
                  file=sys.stderr)
