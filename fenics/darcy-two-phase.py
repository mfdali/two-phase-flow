"""
Update two-phase-flow 
from Garth N. Wells (gnw20@cam.ac.uk) and Harish Narayanan (harish@simula.no)
at 2010-01-26

This program solves pressure-driven, time-dependent flow of two phases
through porous media.
Strong form:
    (lambda(s)*K)^(-1)*u + grad(p) = 0
                            div(u) = 0
              ds/dt + u.grad(F(s)) = 0,
where,
    lambda(s) = 1.0/mu_rel*s^2 + (1 - s)^2
         F(s) = k_rw(s)/mu_w/(k_rw(s)/mu_w + k_ro(s)/mu_o)
              = s^2/(s^2 + mu_rel*(1 - s)^2).
One can then can post-calculate the velocity of each phase using the
relation: u_j = - (k_rj(s)/mu_j)*K*grad(p).
Weak form:
Find u, p, s in V, such that,
   (v, (lambda*K)^(-1)*u) - (div(v), p) = - (v, pbar*n)_N       (1)
                            (q, div(u)) = 0                     (2)
            (r, ds/dt) - (grad(r), F*u) = - (r, F*u.n)_N        (3)
                             
for all v, q, r in V'.
Model problem:
 -----4-----
 |         |
 1         2
 |         |
 -----3-----
Initial Conditions:
u(x, 0) = 0
p(x, 0) = 0
s(x, 0) = 0 in \Omega
Boundary Conditions:
p(x, t) = 1 - x on \Gamma_{1, 2, 3, 4}
s(x, t) = 1 on \Gamma_1 if u.n < 0
s(x, t) = 0 on \Gamma_{2, 3, 4} if u.n > 0

Parameters:
mu_rel, Kinv, lmbdainv, F, dt, T
This implementation includes functional forms from the deal.II demo
available at: http://www.dealii.org/6.2.1/doxygen/deal.II/step_21.html
"""

__author__    = "Monique F. Dali (mfeitosa@lmmp.mec.puc-rio.br)"
__date__      = "2023-01-02"

from dolfin import *

# Optimise compilation of forms
parameters["form_compiler"]["cpp_optimize"] = True
parameters["form_compiler"]["optimize"] = True

class MyNonlinearProblem(NonlinearProblem):
    def __init__(self, a, L, ffc_parameters):
        NonlinearProblem.__init__(self)
        self.L = L
        self.a = a
        self.reset_sparsity = True
        self.ffc_parameters = ffc_parameters
    def F(self, b, x):
        assemble(self.L, tensor=b, form_compiler_parameters=self.ffc_parameters)
    def J(self, A, x):
        assemble(self.a, tensor=A,
                 form_compiler_parameters=self.ffc_parameters)
        self.reset_sparsity = False

# Computational domain and geometry information
mesh = UnitSquareMesh(64, 64)
n = FacetNormal(mesh)

# Physical parameters, functional forms and boundary conditions
# Relative viscosity of water w.r.t. crude oil
mu_rel = 0.2

# Spatially-varying permeability matrix (inverse)
kinv = Expression("1.0/std::max(exp(-pow((x[1] - 0.5 - 0.1*sin(10*x[0]))/0.1, 2.0)), 0.01)", degree=2)
zero = Expression("0.0",degree=1)
Kinv = as_matrix(((kinv, zero), (zero, kinv)))

# Total mobility
def lmbdainv(s):
    return 1.0/((1.0/mu_rel)*s**2 + (1.0 - s)**2)

# Fractional flow function
def F(s):
    return s**2/(s**2 + mu_rel*(1.0 - s)**2)

# Time step
dt = Constant(0.01)

# Pressure boundary condition
class PressureBC(UserExpression):
    def eval(self, values, x):
        values[0] = 1.0 - x[0]

# Saturation boundary condition
class SaturationBC(UserExpression):
    def eval(self, values, x):
        if x[0] < DOLFIN_EPS:
            values[0] =  1.0

# Function spaces
order = 1
BDM = FiniteElement("BDM", mesh.ufl_cell(), order)
DG = FiniteElement("DG", mesh.ufl_cell(), order - 1)

mixed_space = FunctionSpace(mesh, MixedElement(BDM,DG,DG))

ffc_compiler_parameters = {"quadrature_degree": order + 1}

# Function spaces and functions
V  = TestFunction(mixed_space)
dU = TrialFunction(mixed_space)
U  = Function(mixed_space, name="field")
U0 = Function(mixed_space, name="prefield")

v,  q,  r  = split(V)
u,  p,  s  = split(U)
u0, p0, s0 = split(U0)

s_mid = 0.5*(s0 + s)

pbar = PressureBC(degree=1)
sbar = SaturationBC(degree=1)

# Variational forms and problem
L1 = inner(v, lmbdainv(s_mid)*Kinv*u)*dx - div(v)*p*dx + inner(v, pbar*n)*ds
L2 = q*div(u)*dx

# Upwind normal velocity: (inner(v, n) + |inner(v, n)|)/2.0 
# (using velocity from previous step on facets)
# *** Use 0.5*u instead of u/2 to get around FFC bug when optimisations is on
un   = 0.5*(inner(u0, n) + sqrt(inner(u0, n)*inner(u0, n)))
un_h = 0.5*(inner(u0, n) - sqrt(inner(u0, n)*inner(u0, n)))
stabilisation = dt('+')*inner(jump(r), un('+')*F(s_mid)('+') - un('-')*F(s_mid)('-'))*dS \
              + dt*r*un_h*sbar*ds
L3 = r*(s - s0)*dx - dt*inner(grad(r), F(s_mid)*u)*dx + dt*r*F(s_mid)*un*ds \
    + stabilisation

# Total L
L = L1 + L2 + L3

# Jacobian
a = derivative(L, U, dU)

problem = MyNonlinearProblem(a, L, ffc_compiler_parameters)
solver  = NewtonSolver()
solver.parameters["absolute_tolerance"] = 1e-12 
solver.parameters["relative_tolerance"] = 1e-6
solver.parameters["maximum_iterations"] = 10

# Save fields to post-processing
u_file = XDMFFile("velocity.xdmf")
p_file = XDMFFile("pressure.xdmf")
s_file = XDMFFile("saturation.xdmf")
# Save saturation at y = 0.5
data_file_time = open('saturation-time_darcy-two-phase.txt', 'a+')

# Initial time
t = 0.0
# Total time
T = 250*float(dt)

#Solve
while t < T:
    t += float(dt)
    U0.assign(U)
    solver.solve(problem, U.vector())
    u, p, s = U.split()
    uh = project(u)
    sh = project(s)

    p_file.write(p, t)
    s_file.write(s, t)
    u_file.write(u, t)
    data_file_time.write("%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g,%.2g\n" % (s((0.00,0.5)),s((0.05,0.5)),s((0.1,0.5)),s((0.15,0.5)),s((0.2,0.5)),s((0.25,0.5)),s((0.3,0.5)),s((0.35,0.5)),s((0.4,0.50)),s((0.45,0.5)),s((0.5,0.5)),s((0.55,0.5)),s((0.6,0.5)),s((0.65,0.5)),s((0.7,0.5)),s((0.75,0.5)),s((0.8,0.5)),s((0.85,0.5)),s((0.9,0.5)),s((0.95,0.5)),s((1.0,0.5))))

data_file_time.close()
