#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
#  =================================================================
#           #     #                 #     #
#           ##    #   ####   #####  ##    #  ######   #####
#           # #   #  #    #  #    # # #   #  #          #
#           #  #  #  #    #  #    # #  #  #  #####      #
#           #   # #  #    #  #####  #   # #  #          #
#           #    ##  #    #  #   #  #    ##  #          #
#           #     #   ####   #    # #     #  ######     #
#
#        ---   The NorNet Testbed for Multi-Homed Systems  ---
#                        https://www.nntb.no
#  =================================================================
#
#  High-Performance Connectivity Tracer (HiPerConTracer)
#  Copyright (C) 2015-2019 by Thomas Dreibholz
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#  Contact: dreibh@simula.no

import collections
import configparser
import datetime
import io
import os
import psycopg2
import pymongo
import re
import shutil
import ripe.atlas.cousteau
import ssl
import socket
import sys


# ###### Print log message ##################################################
def log(logstring):
   print('\x1b[32m' + datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + ': ' + logstring + '\x1b[0m');


# ###### Print warning message ##############################################
def warning(logstring):
   sys.stderr.write('\x1b[31m' + datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + ': WARNING: ' + logstring + '\x1b[0m\n');


# ###### Print error message ################################################
def error(logstring):
   sys.stderr.write(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + ': ERROR: ' + logstring + '\n')


class AtlasMNS:

   # ###### Constructor #####################################################
   def __init__(self):
      # ====== Set defaults =================================================
      self.configuration = {
         'scheduler_dbserver':   "localhost",
         'scheduler_dbport':     "5432",
         'scheduler_dbuser':     "scheduler",
         'scheduler_dbpassword': None,
         'scheduler_database':   "atlasmsdb",
         'scheduler_cafile':     "None",

         'results_dbserver':     "localhost",
         'results_dbport':       "27017",
         'results_dbuser':       "importer",
         'results_dbpassword':   None,
         'results_database':     "atlasmnsdb",
         'results_cafile':       "None",

         'atlas_api_key':        None
      }

   # ###### Load configuration ##############################################
   def loadConfiguration(self, configFileName):
      parsedConfigFile = configparser.RawConfigParser()
      parsedConfigFile.optionxform = str   # Make it case-sensitive!
      try:
         parsedConfigFile.readfp(io.StringIO(u'[root]\n' + open(configFileName, 'r').read()))
      except Exception as e:
         error('Unable to read database configuration file' +  configFileName + ': ' + str(e))
         return False

      for parameterName in parsedConfigFile.options('root'):
         parameterValue = parsedConfigFile.get('root', parameterName)

         if parameterName == 'scheduler_dbserver':
            self.configuration['scheduler_dbserver'] = parameterValue
         elif parameterName == 'scheduler_dbport':
            self.configuration['scheduler_dbport'] = parameterValue
         elif parameterName == 'scheduler_dbuser':
            self.configuration['scheduler_dbuser'] = parameterValue
         elif parameterName == 'scheduler_dbpassword':
            self.configuration['scheduler_dbpassword'] = parameterValue
         elif parameterName == 'scheduler_database':
            self.configuration['scheduler_database'] = parameterValue
         elif parameterName == 'scheduler_cafile':
            self.configuration['scheduler_cafile'] = parameterValue

         elif parameterName == 'results_dbserver':
            self.configuration['results_dbserver'] = parameterValue
         elif parameterName == 'results_dbport':
            self.configuration['results_dbport'] = parameterValue
         elif parameterName == 'results_dbuser':
            self.configuration['results_dbuser'] = parameterValue
         elif parameterName == 'results_dbpassword':
            self.configuration['results_dbpassword'] = parameterValue
         elif parameterName == 'results_database':
            self.configuration['results_database'] = parameterValue
         elif parameterName == 'results_cafile':
            self.configuration['results_cafile'] = parameterValue

         elif parameterName == 'atlas_api_key':
            self.configuration['atlas_api_key'] = parameterValue

         else:
            warning('Unknown parameter ' + parameterName + ' is ignored!')

      return True


   # ###### Connect to RIPE Atlas ###########################################
   def connectToRIPEAtlas(self):
      log('Connecting to the RIPE Atlas server ...')
      atlas_request = ripe.atlas.cousteau.AtlasRequest(
         **{
            "url_path": "/api/v2/anchors"
         }
      )
      result = collections.namedtuple('Result', 'success response')
      (result.success, result.response) = atlas_request.get()
      return (result.success == True)

   # ###### Connect to PostgreSQL scheduler database ########################
   def connectToSchedulerDB(self):
      log('Connecting to the PostgreSQL scheduler database at ' + self.configuration['scheduler_dbserver'] + ' ...')
      self.scheduler_dbCursor = None
      try:
         if self.configuration['scheduler_cafile'] == "IGNORE":   # Ignore TLS certificate
            warning('TLS certificate check for PostgreSQL scheduler database is turned off!')
            self.scheduler_dbConnection = psycopg2.connect(host=str(self.configuration['scheduler_dbserver']),
                                                           port=str(self.configuration['scheduler_dbport']),
                                                           user=str(self.configuration['scheduler_dbuser']),
                                                           password=str(self.configuration['scheduler_dbpassword']),
                                                           dbname=str(self.configuration['scheduler_database']),
                                                           sslmode='require')
         elif self.configuration['scheduler_cafile'] == "None":   # Use default CA settings
            self.scheduler_dbConnection = psycopg2.connect(host=str(self.configuration['scheduler_dbserver']),
                                                           port=str(self.configuration['scheduler_dbport']),
                                                           user=str(self.configuration['scheduler_dbuser']),
                                                           password=str(self.configuration['scheduler_dbpassword']),
                                                           dbname=str(self.configuration['scheduler_database']),
                                                           sslmode='verify-ca')
         else:   # Use given CA
            self.scheduler_dbConnection = psycopg2.connect(host=str(self.configuration['scheduler_dbserver']),
                                                           port=str(self.configuration['scheduler_dbport']),
                                                           user=str(self.configuration['scheduler_dbuser']),
                                                           password=str(self.configuration['scheduler_dbpassword']),
                                                           dbname=str(self.configuration['scheduler_database']),
                                                           sslmode='verify-ca',
                                                           sslrootcert=self.configuration['scheduler_cafile'])
         self.scheduler_dbConnection.autocommit = False
      except Exception as e:
         error('Unable to connect to the PostgreSQL scheduler database at ' +
               self.configuration['scheduler_dbserver'] + ': ' + str(e))
         return False

      self.scheduler_dbCursor = self.scheduler_dbConnection.cursor()
      return True


   # ###### Connect to MongoDB results database #############################
   def connectToResultsDB(self):
      log('Connecting to MongoDB results database at ' + self.configuration['results_dbserver'] + ' ...')
      try:
         if self.configuration['results_cafile'] == "IGNORE":   # Ignore TLS certificate
            warning('TLS certificate check for MongoDB results database is turned off!')
            results_dbConnection = pymongo.MongoClient(host=str(self.configuration['results_dbserver']),
                                                       port=int(self.configuration['results_dbport']),
                                                       ssl=True, ssl_cert_reqs=ssl.CERT_NONE)
         elif self.configuration['results_cafile'] == "None":   # Use default CA settings
            results_dbConnection = pymongo.MongoClient(host=str(self.configuration['results_dbserver']),
                                                       port=int(self.configuration['results_dbport']),
                                                       ssl=True, ssl_cert_reqs=ssl.CERT_REQUIRED)
         else:   # Use given CA, requires PyMongo >= 3.4!
            results_dbConnection = pymongo.MongoClient(host=str(self.configuration['results_dbserver']),
                                                       port=int(self.configuration['results_dbport']),
                                                       ssl=True, ssl_cert_reqs=ssl.CERT_REQUIRED,
                                                       ssl_ca_certs=self.configuration['results_cafile'])
         self.results_db = results_dbConnection[str(self.configuration['results_database'])]
         self.results_db.authenticate(str(self.configuration['results_dbuser']),
                                      str(self.configuration['results_dbpassword']),
                                      mechanism='SCRAM-SHA-1')
      except Exception as e:
         error('Unable to connect to the MongoDB results database at ' +
               self.configuration['results_dbserver'] + ': ' + str(e))
         return False

      return True