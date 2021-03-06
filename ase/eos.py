# -*- coding: utf-8 -*-
from __future__ import print_function, division

from ase.units import kJ

import numpy as np

try:
    from scipy.optimize import curve_fit
except ImportError:
    try:
        from scipy.optimize import leastsq

        # this part comes from
        # http://projects.scipy.org/scipy/browser/trunk/scipy/optimize/minpack.py
        def _general_function(params, xdata, ydata, function):
            return function(xdata, *params) - ydata
        # end of this part

        def curve_fit(f, x, y, p0):
            func = _general_function
            args = (x, y, f)
            # this part comes from
            # http://projects.scipy.org/scipy/browser/trunk/scipy/optimize/minpack.py
            popt, pcov, infodict, mesg, ier = leastsq(func, p0, args=args,
                                                      full_output=1)

            if ier not in [1, 2, 3, 4]:
                raise RuntimeError("Optimal parameters not found: " + mesg)
            # end of this part
            return popt, pcov
    except ImportError:
        curve_fit = None


eos_names = ['sj', 'taylor', 'murnaghan', 'birch', 'birchmurnaghan',
             'pouriertarantola', 'vinet', 'antonschmidt', 'p3']


def taylor(V, E0, beta, alpha, V0):
    'Taylor Expansion up to 3rd order about V0'

    E = E0 + beta / 2 * (V - V0)**2 / V0 + alpha / 6 * (V - V0)**3 / V0
    return E


def murnaghan(V, E0, B0, BP, V0):
    'From PRB 28,5480 (1983'

    E = E0 + B0 * V / BP * (((V0 / V)**BP) / (BP - 1) + 1) - V0 * B0 / (BP - 1)
    return E


def birch(V, E0, B0, BP, V0):
    """
    From Intermetallic compounds: Principles and Practice, Vol. I: Principles
    Chapter 9 pages 195-210 by M. Mehl. B. Klein, D. Papaconstantopoulos
    paper downloaded from Web

    case where n=0
    """

    E = (E0 +
         9 / 8 * B0 * V0 * ((V0 / V)**(2 / 3) - 1)**2 +
         9 / 16 * B0 * V0 * (BP - 4) * ((V0 / V)**(2 / 3) - 1)**3)
    return E


def birchmurnaghan(V, E0, B0, BP, V0):
    'BirchMurnaghan equation from PRB 70, 224107'

    eta = (V0 / V)**(1 / 3)
    E = E0 + 9 * B0 * V0 / 16 * (eta**2 - 1)**2 * (
        6 + BP * (eta**2 - 1) - 4 * eta**2)
    return E


def check_birchmurnaghan():
    from sympy import symbols, Rational, diff, simplify
    v, b, bp, v0 = symbols('v b bp v0')
    x = (v0 / v)**Rational(2, 3)
    e = 9 * b * v0 * (x - 1)**2 * (6 + bp * (x - 1) - 4 * x) / 16
    print(e)
    B = diff(e, v, 2) * v
    BP = -v * diff(B, v) / b
    print(simplify(B.subs(v, v0)))
    print(simplify(BP.subs(v, v0)))


def pouriertarantola(V, E0, B0, BP, V0):
    'Pourier-Tarantola equation from PRB 70, 224107'

    eta = (V / V0)**(1 / 3)
    squiggle = -3 * np.log(eta)

    E = E0 + B0 * V0 * squiggle**2 / 6 * (3 + squiggle * (BP - 2))
    return E


def vinet(V, E0, B0, BP, V0):
    'Vinet equation from PRB 70, 224107'

    eta = (V / V0)**(1 / 3)

    E = (E0 + 2 * B0 * V0 / (BP - 1)**2 *
         (2 - (5 + 3 * BP * (eta - 1) - 3 * eta) *
          np.exp(-3 * (BP - 1) * (eta - 1) / 2)))
    return E


def antonschmidt(V, Einf, B, n, V0):
    """From Intermetallics 11, 23-32 (2003)

    Einf should be E_infinity, i.e. infinite separation, but
    according to the paper it does not provide a good estimate
    of the cohesive energy. They derive this equation from an
    empirical formula for the volume dependence of pressure,

    E(vol) = E_inf + int(P dV) from V=vol to V=infinity

    but the equation breaks down at large volumes, so E_inf
    is not that meaningful

    n should be about -2 according to the paper.

    I find this equation does not fit volumetric data as well
    as the other equtions do.
    """

    E = B * V0 / (n + 1) * (V / V0)**(n + 1) * (np.log(V / V0) -
                                                (1 / (n + 1))) + Einf
    return E


def p3(V, c0, c1, c2, c3):
    'polynomial fit'

    E = c0 + c1 * V + c2 * V**2 + c3 * V**3
    return E


def parabola(x, a, b, c):
    """parabola polynomial function

    this function is used to fit the data to get good guesses for
    the equation of state fits

    a 4th order polynomial fit to get good guesses for
    was not a good idea because for noisy data the fit is too wiggly
    2nd order seems to be sufficient, and guarantees a single minimum"""

    return a + b * x + c * x**2


class EquationOfState:
    """Fit equation of state for bulk systems.

    The following equation is used::

        sjeos (default)
            A third order inverse polynomial fit 10.1103/PhysRevB.67.026103

            ::

                                    2      3        -1/3
                E(V) = c + c t + c t  + c t ,  t = V
                        0   1     2      3

        taylor
            A third order Taylor series expansion about the minimum volume

        murnaghan
            PRB 28, 5480 (1983)

        birch
            Intermetallic compounds: Principles and Practice,
            Vol I: Principles. pages 195-210

        birchmurnaghan
            PRB 70, 224107

        pouriertarantola
            PRB 70, 224107

        vinet
            PRB 70, 224107

        antonschmidt
            Intermetallics 11, 23-32 (2003)

        p3
            A third order polynomial fit

    Use::

        eos = EquationOfState(volumes, energies, eos='murnaghan')
        v0, e0, B = eos.fit()
        eos.plot()

    """
    def __init__(self, volumes, energies, eos='sj'):
        self.v = np.array(volumes)
        self.e = np.array(energies)

        if eos == 'sjeos':
            eos = 'sj'
        self.eos_string = eos
        self.v0 = None

    def fit(self):
        """Calculate volume, energy, and bulk modulus.

        Returns the optimal volume, the minimum energy, and the bulk
        modulus.  Notice that the ASE units for the bulk modulus is
        eV/Angstrom^3 - to get the value in GPa, do this::

          v0, e0, B = eos.fit()
          print(B / kJ * 1.0e24, 'GPa')

        """

        if self.eos_string == 'sj':
            return self.fit_sjeos()

        self.func = globals()[self.eos_string]

        p0 = [min(self.e), 1, 1]
        popt, pcov = curve_fit(parabola, self.v, self.e, p0)

        parabola_parameters = popt
        # Here I just make sure the minimum is bracketed by the volumes
        # this if for the solver
        minvol = min(self.v)
        maxvol = max(self.v)

        # the minimum of the parabola is at dE/dV = 0, or 2 * c V +b =0
        c = parabola_parameters[2]
        b = parabola_parameters[1]
        a = parabola_parameters[0]
        parabola_vmin = -b / 2 / c

        if not (minvol < parabola_vmin and parabola_vmin < maxvol):
            print('Warning the minimum volume of a fitted parabola is not in '
                  'your volumes. You may not have a minimum in your dataset')

        # evaluate the parabola at the minimum to estimate the groundstate
        # energy
        E0 = parabola(parabola_vmin, a, b, c)
        # estimate the bulk modulus from Vo * E''.  E'' = 2 * c
        B0 = 2 * c * parabola_vmin

        if self.eos_string == 'antonschmidt':
            BP = -2
        else:
            BP = 4

        initial_guess = [E0, B0, BP, parabola_vmin]

        # now fit the equation of state
        p0 = initial_guess
        popt, pcov = curve_fit(self.func, self.v, self.e, p0)

        self.eos_parameters = popt

        if self.eos_string == 'p3':
            c0, c1, c2, c3 = self.eos_parameters
            # find minimum E in E = c0 + c1 * V + c2 * V**2 + c3 * V**3
            # dE/dV = c1+ 2 * c2 * V + 3 * c3 * V**2 = 0
            # solve by quadratic formula with the positive root

            a = 3 * c3
            b = 2 * c2
            c = c1

            self.v0 = (-b + np.sqrt(b**2 - 4 * a * c)) / (2 * a)
            self.e0 = p3(self.v0, c0, c1, c2, c3)
            self.B = (2 * c2 + 6 * c3 * self.v0) * self.v0
        else:
            self.v0 = self.eos_parameters[3]
            self.e0 = self.eos_parameters[0]
            self.B = self.eos_parameters[1]

        return self.v0, self.e0, self.B

    def plot(self, filename=None, show=None, ax=None):
        """Plot fitted energy curve.

        Uses Matplotlib to plot the energy curve.  Use *show=True* to
        show the figure and *filename='abc.png'* or
        *filename='abc.eps'* to save the figure to a file."""

        import matplotlib.pyplot as plt

        if self.v0 is None:
            self.fit()

        if filename is None and show is None:
            show = True

        if ax is None:
            ax = plt.gca()

        x = np.linspace(min(self.v), max(self.v), 100)
        if self.eos_string == 'sj':
            y = self.fit0(x**-(1 / 3))
        else:
            y = self.func(x, *self.eos_parameters)

        ax.plot(x, y, '-r')
        ax.plot(self.v, self.e, 'o')

        try:
            ax.set_xlabel(u'volume [Å$^3$]')
            ax.set_ylabel(u'energy [eV]')
            ax.set_title(u'%s: E: %.3f eV, V: %.3f Å$^3$, B: %.3f GPa' %
                         (self.eos_string, self.e0, self.v0,
                          self.B / kJ * 1.e24))

        except ImportError:  # XXX what would cause this error?  LaTeX?
            ax.set_xlabel(u'volume [L(length)^3]')
            ax.set_ylabel(u'energy [E(energy)]')
            ax.set_title(u'%s: E: %.3f E, V: %.3f L^3, B: %.3e E/L^3' %
                         (self.eos_string, self.e0, self.v0, self.B))

        if show:
            plt.show()
        if filename is not None:
            fig = ax.get_figure()
            fig.savefig(filename)

        return ax

    def fit_sjeos(self):
        """Calculate volume, energy, and bulk modulus.

        Returns the optimal volume, the minimum energy, and the bulk
        modulus.  Notice that the ASE units for the bulk modulus is
        eV/Angstrom^3 - to get the value in GPa, do this::

          v0, e0, B = eos.fit()
          print(B / kJ * 1.0e24, 'GPa')

        """

        fit0 = np.poly1d(np.polyfit(self.v**-(1 / 3), self.e, 3))
        fit1 = np.polyder(fit0, 1)
        fit2 = np.polyder(fit1, 1)

        self.v0 = None
        for t in np.roots(fit1):
            if isinstance(t, float) and t > 0 and fit2(t) > 0:
                self.v0 = t**-3
                break

        if self.v0 is None:
            raise ValueError('No minimum!')

        self.e0 = fit0(t)
        self.B = t**5 * fit2(t) / 9
        self.fit0 = fit0

        return self.v0, self.e0, self.B


def main():
    import optparse
    from ase.io import read
    parser = optparse.OptionParser(usage='python -m ase.eos [options] '
                                   'trajectory, ...',
                                   description='Calculate equation of state.')
    parser.add_option('-p', '--plot', action='store_true')
    parser.add_option('-t', '--type', default='sj')
    opts, args = parser.parse_args()
    if not opts.plot:
        print('# filename                '
              'points     volume    energy  bulk modulus')
        print('#                         '
              '          [Ang^3]      [eV]         [GPa]')
    for name in args:
        if name == '-':
            # Special case - used by ase-gui:
            import pickle
            import sys
            v, e = pickle.load(sys.stdin)
        else:
            if '@' in name:
                index = None
            else:
                index = ':'
            images = read(name, index=index)
            v = [atoms.get_volume() for atoms in images]
            e = [atoms.get_potential_energy() for atoms in images]
        eos = EquationOfState(v, e, opts.type)
        if opts.plot:
            eos.plot()
        else:
            try:
                v0, e0, B = eos.fit()
            except ValueError as ex:
                print('{0:30}{1:2}    {2}'.format(name, len(v), ex.message))
            else:
                print('{0:30}{1:2} {2:10.3f}{3:10.3f}{4:14.3f}'
                      .format(name, len(v), v0, e0, B / kJ * 1.0e24))


if __name__ == '__main__':
    main()
