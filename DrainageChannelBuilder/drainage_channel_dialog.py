# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DrainageChannelBuilderDialog
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

import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import QThread,QFileInfo
import DrainageChannelBuilder_utils as utils
import DrainageChannelThread
from qgis.gui import QgsMessageBar
from qgis.core import QgsMessageLog,QgsRasterLayer,QgsMapLayerRegistry
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib import rcParams
from matplotlib.ticker import ScalarFormatter
from mpl_toolkits.axes_grid.anchored_artists import AnchoredText

import numpy as np

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'drainage_channel_dialog_base.ui'))


class DrainageChannelBuilderDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(DrainageChannelBuilderDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.iface = iface
        self.setupUi(self)
        
        self.resWarning = False        

        

        self.btnOk = self.buttonBox.button(QtGui.QDialogButtonBox.Ok)
        self.btnOk.setText(self.tr("Run 2D"))
        self.btnClose = self.buttonBox.button(QtGui.QDialogButtonBox.Close)  

        
        self.cbDEM.currentIndexChanged.connect(self.updateRasterRes)
        self.cbDEM.currentIndexChanged.connect(self.checkLayerExtents)
        self.cbCL.currentIndexChanged.connect(self.checkLayerExtents)      
        self.spinElevStart.valueChanged.connect(self.calcDepth)
        self.spinElevEnd.valueChanged.connect(self.calcDepth)
        self.spinRightSideSlope.valueChanged.connect(self.updateMaxBankWidth)
        self.spinLeftSideSlope.valueChanged.connect(self.updateMaxBankWidth)   
        self.spinWidth.valueChanged.connect(self.checkRes)
        self.spinRes.valueChanged.connect(self.checkRes)
        self.browseBtn.clicked.connect(self.writeDirName)
        self.btn1Dsave.clicked.connect(self.writeOut1Dresults)
        

        # add matplotlib figure to dialog
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=.1, bottom=0.1, right=.95, top=.9, wspace=None, hspace=.2)
        self.canvas = FigureCanvas(self.figure)
        
        
        self.widgetPlotToolbar = NavigationToolbar(self.canvas, self.widgetPlot)
        lstActions = self.widgetPlotToolbar.actions()
        self.widgetPlotToolbar.removeAction(lstActions[7])
        self.gPlot.addWidget(self.canvas)
        self.gPlot.addWidget(self.widgetPlotToolbar)
        self.figure.patch.set_visible(False)
        
        # and configure matplotlib params
        rcParams["font.serif"] = "Verdana, Arial, Liberation Serif"
        rcParams["font.sans-serif"] = "Tahoma, Arial, Liberation Sans"
        rcParams["font.cursive"] = "Courier New, Arial, Liberation Sans"
        rcParams["font.fantasy"] = "Comic Sans MS, Arial, Liberation Sans"
        rcParams["font.monospace"] = "Courier New, Liberation Mono"

        self.manageGui() 
    
    def manageGui(self):
        print 'manageGui'
        self.cbCL.clear()
        self.cbCL.addItems(utils.getLineLayerNames())
        self.cbDEM.clear()
        self.cbDEM.addItems(utils.getRasterLayerNames())
  
    def refreshPlot(self):
        self.axes.clear()
        
        results1D = utils.getPlotArray(self.vLayer,self.rLayer,self.spinElevStart.value(),self.spinElevEnd.value(),self.xRes)
        
        self.stationA = results1D[0,:]

        self.zExistA = results1D[1,:]
        self.zPropA = results1D[2,:]
        self.xA = results1D[3,:]
        self.yA = results1D[4,:]
        self.calcCutAvgAreaEndMeth()



        self.axes.plot(self.stationA,self.zExistA)
        self.axes.plot(self.stationA,self.zPropA)
        self.axes.grid()
        formatter = ScalarFormatter(useOffset=False)
        self.axes.yaxis.set_major_formatter(formatter)

        self.axes.set_ylabel(unicode(self.tr("Elevation, z field units")))
        self.axes.set_xlabel(unicode(self.tr('Station, layer units')))
        self.axes.set_title(unicode(self.tr('Channel Profile and 1D Calculation Results')))
        at = AnchoredText(self.outText, prop=dict(size=12), frameon=True,loc=1,)
        at.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
        
        self.axes.add_artist(at)
        self.canvas.draw()
        
    def refreshPlotText(self):

        at = AnchoredText(self.outText, prop=dict(size=12), frameon=True,loc=1,)
        at.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
        self.axes.add_artist(at)
        self.canvas.draw()
          
    def calcCutAvgAreaEndMeth(self):
        self.depth1D = self.zExistA - self.zPropA
        
        # find max bank width based on CL depth
        self.maxCLdepth = np.max(self.depth1D)
        leftSlope = self.spinLeftSideSlope.value()
        rightSlope = self.spinRightSideSlope.value()
        width = self.spinWidth.value()
        self.area = self.depth1D*(width + self.depth1D*leftSlope/2.0 + self.depth1D*rightSlope/2.0)
        self.length = self.stationA[1:] - self.stationA[:-1]
        self.vol1D = (self.area[1:] + self.area[:-1])*self.length/2.0
        self.vol1D = np.append(0,self.vol1D)
        self.totVol1D = np.sum(self.vol1D)
        self.maxDepth1D = np.max(self.depth1D)
        self.totLength = np.max(self.stationA)
        self.channelSlope = (self.zPropA[-1]-self.zPropA[0])/self.totLength
        self.outText = 'Length: {2:.2f}\nChannel Slope: {3:.6f}\n1D Max. Cut Depth: {0:,.2f}\n1D Tot. Vol.: {1:,.2f}'.format(self.maxDepth1D,self.totVol1D,self.totLength,self.channelSlope) 

        #self.canvas.draw() 

    def writeOut1Dresults(self):
        # assign results to numpy array for quick csv dump
        self.out1Dresults = np.zeros((self.stationA.size,8))
        self.out1Dresults[:,0] = self.stationA
        self.out1Dresults[:,1] = self.vol1D
        self.out1Dresults[:,2] = self.zExistA
        self.out1Dresults[:,3] = self.zPropA
        self.out1Dresults[:,4] = self.depth1D
        self.out1Dresults[:,5] = self.area
        self.out1Dresults[:,6] = self.xA
        self.out1Dresults[:,7] = self.yA
        outPath = self.outputDir.text()
        home = os.path.expanduser("~")
        if outPath == '':
            outPath = os.path.join(home,'Desktop','QGIS2DrainageChannelBuilderFiles')
            self.outputDir.setText(outPath)
            if not os.path.exists(outPath):
                os.makedirs(outPath)
                
        os.chdir(outPath)
        fileName = 'Channel1Dresults.txt'
        outHeader = 'DEM Layer:\t{0}\nChannel Centerline:\t{1}\nChannel Bottom Width:\t{3}\nChannel Start Elevation:\t{4}\nChannel End Elevation:\t{5}\nChannel Slope:\t{12:.06f}\nLeft Side Slope:\t{6}\nRight Side Slope:\t{7}\nLength:\t{9:,.2f}\n1D Max. Cut Depth:\t{10:,.2f}\n1D Tot. Vol:\t{11:,.2f}\n\nstation\tvol\tzExist\tzProp\tdepth\tcutArea\tx\ty\n'.format(self.cbDEM.currentText(),self.cbCL.currentText(),self.spinRes.value(),self.spinWidth.value(),self.spinElevStart.value(),self.spinElevEnd.value(),self.spinLeftSideSlope.value(),self.spinRightSideSlope.value(),self.spinBankWidth.value(),self.totLength,self.maxDepth1D,self.totVol1D,self.channelSlope)
        np.savetxt(fileName, self.out1Dresults, fmt = '%.3f', header = outHeader, delimiter = '\t') 
        self.canvas.print_figure('Channel1DresultsFigure')

            
    def updateMaxBankWidth(self):
        
        self.maxBankWidth = self.maxCLdepth*np.max(np.array([self.spinLeftSideSlope.value(),self.spinRightSideSlope.value()]))
        self.spinBankWidth.setValue(self.maxBankWidth+self.spinRes.value()/2.)
        self.calcCutAvgAreaEndMeth()
        self.refreshPlotText()

        
        

    def writeDirName(self):
        self.outputDir.clear()
        self.dirName = QtGui.QFileDialog.getExistingDirectory(self, 'Select Output Directory')
        self.outputDir.setText(self.dirName)


        
    def updateRasterRes(self):

        layer = utils.getRasterLayerByName(self.cbDEM.currentText().split(' EPSG')[0])
        if layer.isValid():
            self.xRes = layer.rasterUnitsPerPixelX()
            self.yRes = layer.rasterUnitsPerPixelY()
            self.labelDEMres.setText('DEM Layer Resolution = {:.2f} X {:.2f} Y'.format(self.xRes,self.yRes))
           
    def checkRes(self):

        if self.spinWidth.value()<=self.spinRes.value()*10:
            
            self.resWarning = True
            self.errOutput()
        else:
            self.resWarning = False
            self.errOutput()
        self.calcCutAvgAreaEndMeth()
        self.refreshPlotText()



    def checkLayerExtents(self):

        self.rLayer = utils.getRasterLayerByName(self.cbDEM.currentText().split(' EPSG')[0])
        self.vLayer = utils.getVectorLayerByName(self.cbCL.currentText().split(' EPSG')[0])
        try:
            if self.rLayer.isValid() and self.vLayer.isValid(): 
                if self.rLayer.extent().xMaximum()>=self.vLayer.extent().xMaximum() and self.rLayer.extent().xMinimum()<=self.vLayer.extent().xMinimum() and self.rLayer.extent().yMaximum()>=self.vLayer.extent().yMaximum() and self.rLayer.extent().yMinimum()<=self.vLayer.extent().yMinimum():
                    self.layersOverlap = True
                    self.calcElev()
                    self.btn1Dsave.setEnabled(True)
                    self.btnOk.setEnabled(True)
                    self.errOutput()

                else:
                   self.btnOk.setEnabled(False)
                   self.spinElevStart.setEnabled(False)
                   self.spinElevEnd.setEnabled(False)
                   self.layersOverlap = False
                   self.errOutput()
        except:
            self.btnOk.setEnabled(False)
            self.spinElevStart.setEnabled(False)
            self.spinElevEnd.setEnabled(False)
            self.btn1Dsave.setEnabled(False)
            self.overlayError = True
            self.layersOverlap = False
            self.errOutput()
            pass
        
    def calcDepth(self):
        if self.layersOverlap:

            self.layersOverlap = utils.calcDepth(self)
        if self.layersOverlap:
            self.refreshPlot()
            
    def calcElev(self):
        if self.layersOverlap:
            self.spinElevStart.setEnabled(True)
            self.spinElevEnd.setEnabled(True)
            self.spinElevStart.setValue(utils.calcElev(self)[0])
            self.spinElevEnd.setValue(utils.calcElev(self)[1])
            self.refreshPlot()
            
    
    def updateProgressText(self,message):
        self.labelProgress.setText(message)
        
    def updateOutputText(self,message):
        self.textBrowser.setPlainText(message)
    
    def workerError(self, e, exception_string):
        print 'workerError\n{}\n'.format(exception_string)
        QgsMessageLog.logMessage('Worker thread raised an exception:\n{}'.format(exception_string), level=QgsMessageLog.CRITICAL)
        self.iface.messageBar().pushMessage("Drainge Channel Builder",'It didnt work, see log for details', level=QgsMessageBar.CRITICAL, duration=3)
        self.progressBar.setMaximum(100)
        self.btnOk.setEnabled(True)
        self.btn1Dsave.setEnabled(True)
        
        
    def stopWorker(self):
        self.worker.kill()
        if self.worker is not None:

            self.worker.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            
    def errOutput(self):
        if self.resWarning and not self.layersOverlap:
            self.labelErrMessage.setText('Error: Vector is not completely within raster domain\nWarning: For best 2D results, channel bottom width should be at least ten times greater than 2D grid calculation resolution')
        elif self.resWarning:
            self.labelErrMessage.setText('Warning: For best 2D results, channel bottom width should be at least ten times greater than 2D grid calculation resolution')
        elif not self.layersOverlap:
            self.labelErrMessage.setText('Error: Vector is not completely within raster domain')
        else:
            self.labelErrMessage.setText('')
            
        
    def workerFinished(self,values):
       # print 'values = ',values
        self.stopWorker()
        self.values = values
        maxCut = values[0][0]
        avgCut = values[0][1]
        totVol = values[0][2]
        self.dirName = values[0][3]
        self.outputDir.setText(self.dirName)
        demChannelPath = values[0][4]
        demCutDepth = values[0][5]
        length = values[0][6]
        outText = 'Summary of 2D Results:\nLength\t{3:,.2f}\nMax. Cut Depth\t{0:.2f}\nAvg. Cut Depth\t{1:.2f}\nTot. Vol.\t{2:,.2f}'.format(maxCut,avgCut,totVol,length)
        self.updateOutputText(outText)

#            for layer in self.layers:
#                utils.addSlLayer(self.iface,self.dbase,layer)

        self.iface.messageBar().pushMessage("Drainge Channel Builder", 'Channel elevation DEM, channel depth of cut DEM, and channel grid points located at {}.  Please delete when finished'.format(self.dirName),duration=30)
        
        # set channel dem qml by coping dem layer style to channel dem qml
        self.rLayer.saveNamedStyle(os.path.join(self.dirName,demChannelPath.split('.tif')[0]+'.qml'))
        
        # set depth qml w/ function
        xmlString = utils.depthQMLwriter(maxCut)
        demCutDepthQML = open(demCutDepth.split('.tif')[0]+'.qml','w')
        demCutDepthQML.write(xmlString)
        demCutDepthQML.close()
        
        
        if self.checkBoxLoadLayers.checkState():
            for fileName in [demChannelPath,demCutDepth]:
                fileInfo = QFileInfo(fileName)
                baseName = fileInfo.baseName()
                layer = QgsRasterLayer(fileName, baseName)
                if not layer.isValid():
                    print "Layer failed to load!"
                QgsMapLayerRegistry.instance().addMapLayer(layer)
        
        self.progressBar.setMaximum(100)
        self.cbCL.setEnabled(True)
        self.cbDEM.setEnabled(True)
        self.spinRes.setEnabled(True)
        self.spinWidth.setEnabled(True)
        self.spinElevStart.setEnabled(True)
        self.spinElevEnd.setEnabled(True)
        self.spinLeftSideSlope.setEnabled(True)
        self.spinRightSideSlope.setEnabled(True)
        self.spinBankWidth.setEnabled(True)
        self.browseBtn.setEnabled(True)
        self.btn1Dsave.setEnabled(True)
        self.btnClose.setEnabled(True)
        self.btnOk.setEnabled(True)


        self.writeOut1Dresults()
        fileName = 'Channel2DresultsSummary.txt'
        outText = 'DEM Layer:\t{0}\nChannel Centerline:\t{1}\n2D Grid Calc Res.:\t{2}\nChannel Bottom Width:\t{3}\nChannel Start Elevation:\t{4}\nChannel End Elevation:\t{5}\nChannel Slope:\t{13:.06f}\nLeft Side Slope:\t{6}\nRight Side Slope:\t{7}\n2D Maximum Bank Width:\t{8}\n\nLength:\t{9:,.2f}\n2D Max. Cut Depth:\t{10:,.2f}\n2D Avg. Cut Depth:\t{11:,.2f}\n2D Tot. Vol:\t{12:,.2f}\n'.format(self.cbDEM.currentText(), self.cbCL.currentText(), self.spinRes.value(), self.spinWidth.value(), self.spinElevStart.value(), self.spinElevEnd.value(), self.spinLeftSideSlope.value(), self.spinRightSideSlope.value(), self.spinBankWidth.value(), self.totLength, maxCut, avgCut, totVol, self.channelSlope)
        outFile = open(fileName,'w') 
        outFile.write(outText)  
        outFile.close()
        



    def accept(self):
        print 'accepted'
        
        args = [self.rLayer,self.vLayer,self.spinWidth.value(),self.spinRes.value(),self.spinElevStart.value(),self.spinElevEnd.value(),self.spinLeftSideSlope.value(),self.spinRightSideSlope.value(),self.spinBankWidth.value(),self.outputDir.text()]
        self.thread = QThread() 
        # create a new worker instance
        self.worker = DrainageChannelThread.DrainageChannelBuilder(args)   
        
             
        
        # create a new worker instance
        self.worker.moveToThread(self.thread)
        self.worker.updateProgressText.connect(self.updateProgressText)
        
        

        self.worker.workerFinished.connect(self.workerFinished)
        self.worker.error.connect(self.workerError)
        


        self.btnClose.setEnabled(False)
        self.cbCL.setEnabled(False)
        self.cbDEM.setEnabled(False)
        self.spinRes.setEnabled(False)
        self.spinWidth.setEnabled(False)
        self.spinElevStart.setEnabled(False)
        self.spinElevEnd.setEnabled(False)
        self.spinLeftSideSlope.setEnabled(False)
        self.spinRightSideSlope.setEnabled(False)
        self.spinBankWidth.setEnabled(False)
        self.browseBtn.setEnabled(False)
        self.btn1Dsave.setEnabled(False)
        self.btnOk.setEnabled(False)
        self.tabWidgetOutput.setCurrentWidget(self.tabOutputSummary)


        #self.buttonBox.rejected.disconnect(self.reject)
        
        
        self.progressBar.setMaximum(0)
        self.thread.started.connect(self.worker.run)
        self.thread.start()
        


        
    def reject(self):
        print 'rejected'
        QtGui.QDialog.reject(self)
