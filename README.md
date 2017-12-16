# GRASS-GIS-SOS-tools
My Google Summer of Code 2017 project. Most parts of this project were created
during the GSoC 2017.

Modules can be used as python scripts or you can make them with command:
```
sudo make MODULE_TOPDIR=*your_grass_folder*
```
Then you can use them same way as common modules.

In the future, modules should be accesible through the
[GRASS SVN repository](https://svn.osgeo.org/grass/grass-addons/)

## What do you need to test these AddOns? 
To use this module, you need your OWSLib 0.15.0 or newer. If you don't have it,
you can install it from its
[github repository](https://github.com/geopython/OWSLib).

Because of granularity options, you need to be using GRASS > 7.2 to have access
to some functions.

