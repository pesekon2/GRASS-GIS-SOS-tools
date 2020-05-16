#!/usr/bin/env python3
#
############################################################################
#
# MODULE:	    t.vect.to.rast
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Convert a space time vector dataset into a space time raster
#               dataset
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Convert stvds into a space time raster raster dataset
#% keyword: vector
#% keyword: raster
#% keyword: temporal
#% keyword: conversion
#%end
#%option G_OPT_STVDS_INPUT
#%end
#%option G_OPT_STRDS_OUTPUT
#%end
#%option
#% key: basename
#% type: string
#% label: Basename of the new generated output maps
#% description: A timestamp will be attached to created raster maps
#% required: yes
#% multiple: no
#%end
#%option
#% key: column
#% type: string
#% description: Name of attribute column with values
#% required: no
#% multiple: no
#% answer: value
#%end


import sys
import copy
import grass.script as gscript
from grass.script import run_command, pipe_command
import grass.temporal as tgis
import grass.pygrass.modules as pymod


def main(options, flags):

    tgis.init()
    dbif = tgis.SQLDatabaseInterfaceConnection()
    dbif.connect()

    oldStds = tgis.open_old_stds(options['input'], "stvds", dbif)
    stampedMaps = oldStds.get_registered_maps_as_objects(dbif=dbif)

    vectorMaps = get_maps(options['input'])
    rasterMaps = rasterize(options, vectorMaps, stampedMaps, dbif,
                           gscript.overwrite())

    tempType, semanticType, title, description = oldStds.get_initial_values()
    newStds = tgis.open_new_stds(options['output'], 'strds', tempType, title,
                                 description, semanticType, dbif,
                                 overwrite=gscript.overwrite())

    for map in rasterMaps:
        map.load()
        map.insert(dbif)
        newStds.register_map(map, dbif)

    newStds.update_from_registered_maps(dbif)

    dbif.close()


def get_maps(stvds):
    """Get vector maps registered in an input stvds.

    :param stvds: Spatio temporal vector dataset intended to convert
    :return maps: dictionary in format {vector map: [layers of vector map]}
    """

    listOutput = pipe_command('t.vect.list', input=stvds)
    listOutput = listOutput.communicate()[0]
    maps = dict()
    first = True

    for oneMap in listOutput.splitlines():
        if first is False:
            if oneMap.split('|')[0] in maps.keys():
                maps[oneMap.split('|')[0]].append(oneMap.split('|')[1])
            else:
                maps.update({oneMap.split('|')[0]: [oneMap.split('|')[1]]})
        else:
            first = False

    return maps


def rasterize(options, vectorMaps, stampedMaps, dbif, overwrite):
    """Rasterize all vector maps and return a list of their names.

    :param options: Named arguments given when calling module
    :param vectorMaps: Names of vector maps intended to be converted to rasters
    :param stampedMaps: List of vector maps as objects (with timestamps)
    :param dbif: SQL database interface connection
    :param overwrite: boolean saying whether should we overwrite existing maps
    :return rasterMaps: List of names of newly created raster maps
    """

    rasterMaps = list()

    for map, layers in vectorMaps.items():
        for layer in layers:
            for mtimMap in stampedMaps:
                if mtimMap.get_id().split('@')[0] == ':'.join([map, layer]):
                    extent = mtimMap.get_temporal_extent()
                    mapName = '{}_{}'.format(options['basename'],
                                             extent.get_start_time())
                    if ':' in mapName:
                        mapName = '_'.join(mapName.split(':'))
                    if '-' in mapName:
                        mapName = '_'.join(mapName.split('-'))
                    if ' ' in mapName:
                        mapName = '_'.join(mapName.split(' '))

            newMap = tgis.open_new_map_dataset(mapName,
                                               None,
                                               type="raster",
                                               temporal_extent=extent,
                                               dbif=dbif,
                                               overwrite=overwrite)

            run_command('v.to.rast',
                        input=map,
                        layer=layer,
                        use='attr',
                        attribute_column=options['column'],
                        output=newMap.get_id(),
                        quiet=True,
                        overwrite=overwrite)

            rasterMaps.append(newMap)

    return rasterMaps


if __name__ == "__main__":
    options, flags = gscript.parser()
    main(options, flags)
