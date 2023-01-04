# Two-phase-flow
Two phase flow through porous media using FEM or FDM

Scripts to solve two-phase flow in porous media with FEniCS and post-process the results to build GIFs.

# Post-processing
It also creates transitions for transient problems from one timestep graph to the next timestep with Matplotlib's scatter plots, smooth curve plots and Paraview's animation.
Then it uses Matplotlib to draw the sequence plots or Paraview. Builds GIF with ImageIO.

## Fields
![](https://raw.githubusercontent.com/mfdali/two-phase-flow/main/fenics/darcy-two-zones_gif.gif)

## Curves
![]('https://raw.githubusercontent.com/mfdali/two-phase-flow/main/fenics/sat_front_gif.gif')

##Dots
![]('https://raw.githubusercontent.com/mfdali/two-phase-flow/main/fenics/terzaghi_gif.gif')

# Libraries
FEniCS
Matplotlib
ImageIO
Pandas
Math
Numpy
