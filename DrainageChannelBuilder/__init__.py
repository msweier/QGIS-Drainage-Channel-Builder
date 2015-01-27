# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DrainageChannelBuilder
                                 A QGIS plugin
 This plugin will cut a simple, trapezoidal drainage channel in a DEM and calculate the cut volume.
                             -------------------
        begin                : 2015-01-07
        copyright            : (C) 2015 by Mitchell Weier - North Dakota State Water Commission
        email                : mweier@nd.gov
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DrainageChannelBuilder class from file DrainageChannelBuilder.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .drainage_channel import DrainageChannelBuilder
    return DrainageChannelBuilder(iface)
