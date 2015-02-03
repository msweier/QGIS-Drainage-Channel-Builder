# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DrainageChannelBuilder
                                 A QGIS plugin
 This plugin will cut a simple, trapezoidal drainage channel in a DEM and calculate the cut volume.
                              -------------------
        begin                : 2015-01-07
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Mitchell Weier - North Dakota State Water Commission
        email                : mweier@nd.gov
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import locale

#from PyQt4.QtCore import QSettings
#import platform
from shapely.wkb import loads
import numpy as np
#from PyQt4.QtGui import *

from qgis.core import QgsMapLayerRegistry, QGis, QgsRaster, QgsMapLayer, QgsPoint
#from qgis.gui import *

def frange(start, end, step):
  while start < end:
    yield start
    start += step

def getLineLayerNames():
    layerMap = QgsMapLayerRegistry.instance().mapLayers()
    layerNames = []
    for name, layer in layerMap.iteritems():
        if layer.type() == QgsMapLayer.VectorLayer and layer.wkbType()==QGis.WKBLineString and int(layer.featureCount())==1:
            srs = layer.crs().authid()
            layerNames.append(unicode(layer.name())+' '+srs)
    return sorted(layerNames, cmp=locale.strcoll)
    
def getRasterLayerNames():
    layerMap = QgsMapLayerRegistry.instance().mapLayers()
    layerNames = []
    for name, layer in layerMap.iteritems():
        if layer.type() == QgsMapLayer.RasterLayer and layer.providerType() != 'wms':
            srs = layer.crs().authid()
            layerNames.append(unicode(layer.name()+' '+srs))
    return sorted(layerNames, cmp=locale.strcoll)
    
def getVectorLayerByName(layerName):
    layerMap = QgsMapLayerRegistry.instance().mapLayers()
    for name, layer in layerMap.iteritems():
        if layer.type() == QgsMapLayer.VectorLayer and layer.name() == layerName:
            if layer.isValid():
                return layer
            else:
                return None
                
def getRasterLayerByName(layerName):
    layerMap = QgsMapLayerRegistry.instance().mapLayers()
    for name, layer in layerMap.iteritems():
        if layer.type() == QgsMapLayer.RasterLayer and layer.name() == layerName:
            if layer.isValid():
                return layer
            else:
                return None
                
def valRaster(x,y,rLayer):

    z = rLayer.dataProvider().identify(QgsPoint(x,y), QgsRaster.IdentifyFormatValue).results()[1]
    return z
    
def calcElev(self):
  
    features = self.vLayer.getFeatures()
    for f in features:
        geom = f.geometry()
    startPoint = geom.asPolyline()[0]
    endPoint = geom.asPolyline()[-1]
    try:
        startPointZdem = valRaster(startPoint[0],startPoint[1],self.rLayer)
    except:
        startPointZdem =None
        self.labelStartDepth.setText('Start point outside of raster')
        self.btnOk.setEnabled(False)
    try:        
        endPointZdem = valRaster(endPoint[0],endPoint[1],self.rLayer)
    except:
        endPointZdem =None
        self.labelStartDepth.setText('End point outside of raster')
        self.btnOk.setEnabled(False)
    return [startPointZdem, endPointZdem]
    
def getPlotArray(vLayer,rLayer,zStart,zEnd,res):
    # transform vector into in Shapely        
    features = vLayer.getFeatures()
    for f in features:

        geom = f.geometry()
    clSHP = loads(geom.asWkb())
    zPropSlope = (zStart-zEnd)/clSHP.length
    pClXYZd = Zcalc(clSHP,zStart,zPropSlope,res)
    station = pClXYZd[3]
    zProp = pClXYZd[2]
    zExisting = []
    #print zip(pClXYZd[0],pClXYZd[0])
    for xy in zip(pClXYZd[0],pClXYZd[1]):
        x,y = xy
        z = valRaster(x,y,rLayer)
        zExisting.append(z)


    return np.array([np.array(station), np.array(zExisting), np.array(zProp), np.array(pClXYZd[0]), np.array(pClXYZd[1])])
    
    
def depthQMLwriter(maxVal):
    xmlTemplate = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="2.6.1-Brighton" minimumScale="0" maximumScale="1e+08" hasScaleBasedVisibilityFlag="0">
  <pipe>
    <rasterrenderer opacity="1" alphaBand="-1" classificationMax="{0:.02f}" classificationMinMaxOrigin="User" band="1" classificationMin="0" type="singlebandpseudocolor">
      <rasterTransparency/>
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" clip="0">
          <item alpha="255" value="0" label="0.00" color="#fff5eb"/>
          <item alpha="255" value="{1:.02f}" label="{1:.02f}" color="#fee6cf"/>
          <item alpha="255" value="{2:.02f}" label="{2:.02f}" color="#fdd1a5"/>
          <item alpha="255" value="{3:.02f}" label="{3:.02f}" color="#fdb171"/>
          <item alpha="255" value="{4:.02f}" label="{4:.02f}" color="#fd9243"/>
          <item alpha="255" value="{5:.02f}" label="{5:.02f}" color="#f36f1a"/>
          <item alpha="255" value="{6:.02f}" label="{6:.02f}" color="#de4f05"/>
          <item alpha="255" value="{7:.02f}" label="{7:.02f}" color="#b03902"/>
          <item alpha="255" value="{0:.02f}" label="{0:.02f}" color="#7f2704"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation colorizeGreen="3" colorizeOn="0" colorizeRed="240" colorizeBlue="3" grayscaleMode="0" saturation="0" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
""".format(maxVal,maxVal*1/8,maxVal*2/8,maxVal*3/8,maxVal*4/8,maxVal*5/8,maxVal*6/8,maxVal*7/8)
    return xmlTemplate


def calcDepth(self):
    startPointZdem, endPointZdem = calcElev(self)  
    try:
        startDepth = startPointZdem -self.spinElevStart.value()
        self.labelStartDepth.setText('Start Depth = {:.2f}'.format(startDepth))
    except:
        startDepth =None
        self.labelStartDepth.setText('Start point outside of raster')
        self.btnOk.setEnabled(False)
        self.layersOverlap = False
    try:
        endDepth = endPointZdem -self.spinElevEnd.value()
        self.labelEndDepth.setText('End Depth = {:.2f}'.format(endDepth))
    except:
        endDepth = None
        self.labelEndDepth.setText('End point outside of raster')
        self.btnOk.setEnabled(False)
        self.layersOverlap = False
    if startDepth and endDepth:
        self.btnOk.setEnabled(True)
        self.layersOverlap = True
    return self.layersOverlap

def elevationSampler(vectSHP,res,raster):
    "Returns xyz and station distance list from 2d vector and DEM at specified resolution"
    x = []
    y = []
    z = []
    dist = []
    vectLength=vectSHP.length
    for currentDist  in frange(0,vectLength,res):  
        # creation of the point on the line
        point = vectSHP.interpolate(currentDist)
        xp,yp=point.x, point.y
        x.append(xp)
        y.append(yp)
        # extraction of the elevation value from the point
        zp=valRaster(x,y,raster)
        z.append(zp)
        dist.append(currentDist)
        xyzdList = [x,y,z,dist]
    return xyzdList
    
def Zcalc(vectSHP,zStart,zPropSlope,res):
    x = []
    y = []
    z = []
    dist = []
    
    vectLength = vectSHP.length
    for currentDist  in frange(0,vectLength,res):
        point = vectSHP.interpolate(currentDist) 
        xp,yp = point.x, point.y
        x.append(xp)
        y.append(yp)

        z.append(zStart-currentDist*zPropSlope)
        dist.append(currentDist)
        xyzdList = [x,y,z,dist]

    return xyzdList     
    
def channelPoints(vLayer,raster,startElev,endElev,width,leftSideSlope,rightSideSlope,bankWidth,res):
    "Returns xyz and station distance list for channel centerline, toe slopes, and top slopes at vertcies for specified elevation, width, and side slope"
    
    # transform vector into in Shapely        
    features = vLayer.getFeatures()
    for f in features:
        geom = f.geometry()
    clSHP = loads(geom.asWkb())


    
    lToe = clSHP.parallel_offset(width/2.0,'left')
    rToe = clSHP.parallel_offset(width/2.0,'right')
    # right offset reverses coordinate order, reverse them back
    rToe.coords = rToe.coords[::-1]
    
    lTop = lToe.parallel_offset(bankWidth,'left')
    rTop = rToe.parallel_offset(bankWidth,'right')
    # right offset reverses coordinate order, reverse them back
    rTop.coords = rTop.coords[::-1]
    
    
#    zStart = valRaster(clSHP.coords[0][0],clSHP.coords[0][1],raster)-startDepth
#    zEnd = valRaster(clSHP.coords[-1][0],clSHP.coords[-1][1],raster)-endDepth
    zStart = startElev
    zEnd = endElev
    zPropSlope = (zStart-zEnd)/clSHP.length


    pClXYZd = Zcalc(clSHP,zStart,zPropSlope,res)
    lToeXYZd = Zcalc(lToe,zStart,zPropSlope,res)
    rToeXYZd = Zcalc(rToe,zStart,zPropSlope,res)
    lTopXYZd = Zcalc(lTop,zStart+bankWidth/leftSideSlope,zPropSlope,res)
    rTopXYZd = Zcalc(rTop,zStart+bankWidth/rightSideSlope,zPropSlope,res)

    x = lTopXYZd[0] + lToeXYZd[0] + pClXYZd[0] + rToeXYZd[0] + rTopXYZd[0]
    y = lTopXYZd[1] + lToeXYZd[1] + pClXYZd[1] + rToeXYZd[1] + rTopXYZd[1]
    z = lTopXYZd[2] + lToeXYZd[2] + pClXYZd[2] + rToeXYZd[2] + rTopXYZd[2]

    
    # interpolate channel from cL to toe both sides
    
    if width/2 >=res: 

        for i in frange(res,width/2.0 ,res):
            #print i
            leftStep = clSHP.parallel_offset(i,'left')
            rightStep = clSHP.parallel_offset(i,'right')
            # right offset reverses coordinate order, reverse them back
            rightStep.coords = rightStep.coords[::-1]
            leftStepXYZd = Zcalc(leftStep,zStart,zPropSlope,res) 
            rightStepXYZd = Zcalc(rightStep,zStart,zPropSlope,res) 
            x = x + leftStepXYZd[0] + rightStepXYZd[0]
            y = y + leftStepXYZd[1] + rightStepXYZd[1]
            z = z + leftStepXYZd[2] + rightStepXYZd[2]
    
    
    # interpolate sideslopes from toe to top for both sides
    for i in frange(res,bankWidth,res):
        #print i
        leftStep = clSHP.parallel_offset(i+width/2.0,'left')
        rightStep = clSHP.parallel_offset(i+width/2.0,'right')
        # right offset reverses coordinate order, reverse them back
        rightStep.coords = rightStep.coords[::-1]
        leftStepXYZd = Zcalc(leftStep,zStart+i/leftSideSlope,zPropSlope,res) 
        rightStepXYZd = Zcalc(rightStep,zStart+i/rightSideSlope,zPropSlope,res) 
        x = x + leftStepXYZd[0] + rightStepXYZd[0]
        y = y + leftStepXYZd[1] + rightStepXYZd[1]
        z = z + leftStepXYZd[2] + rightStepXYZd[2]
        
    
    return pClXYZd,lToeXYZd,rToeXYZd,lTopXYZd,rTopXYZd,x,y,z


