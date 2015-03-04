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

from shapely.geometry import Polygon
from osgeo import ogr, gdal
import numpy as np
from PyQt4.QtCore import QObject, pyqtSignal
import traceback
import time
import DrainageChannelBuilder_utils as utils
import GdalTools_utils as gdalUtils
import os
import platform
import subprocess

            
class DrainageChannelBuilder(QObject):

    workerFinished = pyqtSignal(list)
    workerInterrupted = pyqtSignal()
    updateProgressText = pyqtSignal(str)
    error = pyqtSignal(Exception, basestring)


    def __init__(self,args):
        QObject.__init__(self)

        
        self.killed = False
        self.rLayer,self.vLayer,self.width,self.res,self.startElev,self.endElev,self.leftSideSlope,self.rightSideSlope,self.bankWidth,self.dirName = args
        gdalUtils.setProcessEnvironment(QObject)
        
     

    def run(self):
        t0=time.time()
        self.values=None
        message='starting'

        self.updateProgressText.emit(message)
               
        try:  

            self.DrainageChannelWorker()

        
        except Exception, e:
            # forward the exception upstream
            self.error.emit(e, traceback.format_exc())
            #print traceback.format_exc()



        self.workerFinished.emit([self.values])
        

#        if not self.interrupted:
#            self.workerFinished.emit([self.values])
#        else:
#            self.workerInterrupted.emit()
        

        t1=time.time()
        tdelta = (t1-t0)/60
        message='\nFinished - Runtime was {:6.2f} minutes\n' .format(tdelta)

        self.updateProgressText.emit(message)
         
    def kill(self):
        self.killed = True

    def stop(self):
        self.mutex.lock()
        self.stopMe = 1
        self.mutex.unlock()

        QThread.wait(self)
        
    def DrainageChannelWorker(self):

        home = os.path.expanduser("~")
        if self.dirName == '':
            self.dirName = os.path.join(home,'Desktop','QGIS2DrainageChannelBuilderFiles')
            if not os.path.exists(self.dirName):
                os.makedirs(self.dirName)


        os.chdir(self.dirName)

        epsgCode = self.vLayer.crs().authid()
        # open raster w/ gdal
        fileDEM = self.rLayer.dataProvider().dataSourceUri()

        

        
        
        message='\nCreating point grid of synthetic channel\n'
        self.updateProgressText.emit(message)
        
        
        # return x, y, z point grid of synthetic channel
         
        pCL, lToe, rToe, lTop, rTop, x, y, z = utils.channelPoints(self.vLayer, self.rLayer, self.startElev, self.endElev, self.width, self.leftSideSlope, self.rightSideSlope, self.bankWidth, self.res)
        
        # construct making polygon layer of points
        
        XYZ = zip(x,y,z)       
        polyCoords = zip(lTop[0]+rTop[0][::-1],lTop[1]+rTop[1][::-1]) # rTop[0][::-1] reverses order
        polyShap = Polygon (polyCoords)      
        xMin, yMin, xMax, yMax = polyShap.bounds        
        xSize = int(round((xMax - xMin)/self.res))
        ySize = int(round((yMax - yMin)/self.res))        
        
        
        # write out points to vrt format for gdal_grid
        message='\nWriting out points to vrt format for gdal_grid\n'
        self.updateProgressText.emit(message)
        
        tmpCSV = 'ChannelPoints_{}'.format(self.vLayer.name())
        try:
            os.remove(tmpCSV+'.csv')
            os.remove(tmpCSV+'.vrt')
        except OSError:
            pass
        outCSV = open(tmpCSV+'.csv','w')

        outCSV.write('x,y,z\n')
        for i in XYZ:
            outCSV.write('{:.3f},{:.3f},{:.3f}'.format(i[0],i[1],i[2]))
            if i != XYZ[-1]:
                outCSV.write('\n')   
        outCSV.close()
        outCSVheader = open(tmpCSV+'.vrt','w')
        outCSVheader.write('<OGRVRTDataSource>\n\t<OGRVRTLayer name="{0}">\n\t\t<SrcDataSource relativeToVRT="1">{0}.csv</SrcDataSource>\n\t\t<GeometryType>wkbPoint</GeometryType>\n\t\t<GeometryField encoding="PointFromColumns" x="x" y="y" z="z"/>\n\t</OGRVRTLayer>\n</OGRVRTDataSource>'.format(tmpCSV))
        outCSVheader.close()
        
        # grid channel points
        message='\nGridding synthetic channel points with gdal_grid.py\n'
        self.updateProgressText.emit(message)
        
        tmpChanRast = self.vLayer.name().replace(' ','_')+'ChannelGrid.tif'
        try:
            os.remove(tmpChanRast)
        except OSError:
            pass  
        r1 = r2 = self.res
        inFile = os.path.join(self.dirName,tmpCSV+'.vrt')
        outFile = os.path.join(self.dirName,tmpChanRast)
        cmd = 'gdal_grid -zfield z -a_srs {3} -a nearest:radius1={10}:radius2={11} -outsize {4} {5} -l {0} -txe {6} {7} -tye {8} {9} {1} {2}'.format(tmpCSV,inFile,outFile,epsgCode,xSize,ySize,xMin,xMax,yMin,yMax,r1,r2)
        proc = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stdin=open(os.devnull),stderr=subprocess.STDOUT,universal_newlines=True)
        ff, err = proc.communicate()
        print err        

        
        
        
        # write out outline polygon to file to clip grid channel
        outShape = os.path.join(self.dirName,self.vLayer.name().replace(' ','_')+'Poly.shp').encode('utf-8')
        
        outDriver = ogr.GetDriverByName('Esri Shapefile')
        
        # Remove output shapefile if it already exists
        if os.path.exists(outShape):
            outDriver.DeleteDataSource(outShape)

        outDataSource = outDriver.CreateDataSource(outShape)
        # create output shapefile
        outLayer = outDataSource.CreateLayer(outShape, geom_type = ogr.wkbMultiPolygon)
        # Add one attribute
        outLayer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
        featureDefn = outLayer.GetLayerDefn()
        # Create a new feature (attribute and geometry)
        feat = ogr.Feature(featureDefn)
        feat.SetField('id', 1)
        # Make a geometry, from Shapely object
        geom = ogr.CreateGeometryFromWkb(polyShap.wkb)
        feat.SetGeometry(geom)
        outLayer.CreateFeature(feat)

        outFile = open(outShape.split('.shp')[0] +'.prj', 'w')
        outFile.write(self.vLayer.crs().toWkt())
        outFile.close()
        outDataSource = outLayer = feat = geom = None # destroy these  
        
        # clip channel grid to channel polygon
        message='\nclip DEM to channel polygon\n'
        self.updateProgressText.emit(message)            

        tmpChanRastClip = os.path.join(self.dirName,self.vLayer.name().replace(' ','_')+'ChannelGridClip.tif')
        cmd = 'gdalwarp -t_srs {0} -dstnodata -99999 -q -cutline {1} -crop_to_cutline -te {2} {3} {4} {5} -tr {6} {7} -overwrite {8} {9}'.format(epsgCode,outShape,xMin,yMin,xMax,yMax,self.res,self.res,tmpChanRast,tmpChanRastClip,)
        proc = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stdin=open(os.devnull),stderr=subprocess.STDOUT,universal_newlines=True)
        ff, err = proc.communicate() 	
        print err
   

        ####### insert channel grid into clipped DEM where channelGrid<= clippedDEM
        message='\nInserting synthetic channel grid into DEM where channel elevation is less than DEM\n'
        self.updateProgressText.emit(message)

        # clip DEM to channel polygon
        tmpDEMclip = os.path.join(self.dirName,self.rLayer.name()+'Clip.tif')
        cmd = 'gdalwarp -r bilinear -te {0} {1} {2} {3} -tr {4} {5} -overwrite {6} {7}'.format(xMin,yMin,xMax,yMax,self.res,self.res,fileDEM,tmpDEMclip)
        proc = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stdin=open(os.devnull),stderr=subprocess.STDOUT,universal_newlines=True)
        ff, err = proc.communicate() 	
        print err
        
        # merge clipped DEM and channelGrid
        ### replace .py with .bat if windows
        if platform.system() == "Windows":
            gdal_calc = 'gdal_calc.bat'
        else:
            gdal_calc = 'gdal_calc.py'
        
        
        demChannel = os.path.join(self.dirName,'ChannelElev_{}.tif'.format(self.vLayer.name()))
        cmd = gdal_calc+' -A {0} -B {1} --overwrite --outfile={2} --NoDataValue=0 --calc="B*(B<A)+A*(B>=A)"'.format(tmpDEMclip,tmpChanRastClip,demChannel)
        proc = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stdin=open(os.devnull),stderr=subprocess.STDOUT,universal_newlines=True)
        ff, err = proc.communicate() 	
        print err
        
        # calc cut grid
        
        demCutDepth = os.path.join(self.dirName,'ChannelDepthCut_{}.tif'.format(self.vLayer.name()))
        cmd = gdal_calc+' -A {0} -B {1} --overwrite --outfile={2} --NoDataValue=0 --calc="A*(B<0)+(A-B)*(B>0)"'.format(tmpDEMclip,demChannel,demCutDepth)
        proc = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stdin=open(os.devnull),stderr=subprocess.STDOUT,universal_newlines=True)
        ff, err = proc.communicate() 	
        print err
        
        # open cut depth grid w/ gdal/numpy

        

        ds = gdal.Open(demCutDepth)
        a = np.array(ds.GetRasterBand(1).ReadAsArray())
        maxCut = a.max()
        numPix = np.size(a[np.where(a>0.005)]) # number of pixels not zero
        avgCut = a[np.where(a>0.01)].mean()
        vol = avgCut*numPix*self.res*self.res
        
        channelLength = pCL[3][-1]
        
        
        self.values = maxCut,avgCut,vol,self.dirName,demChannel,demCutDepth, channelLength

        
        removeWorkingFiles = True
        
        if removeWorkingFiles:
            os.remove(tmpDEMclip)
            try:
                os.remove(tmpDEMclip+'.aux.xml')
            except:
                pass
            os.remove(tmpChanRastClip)
            os.remove(tmpChanRast)
            try:
                outDriver.DeleteDataSource(outShape)
            except:
                pass
        

        
        
        return self.values
        
        