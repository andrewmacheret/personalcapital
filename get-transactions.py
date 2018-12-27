#!/usr/bin/env python

from __future__ import print_function
import sys
import csv
import os
#from getpass import getpass
from httplib2 import Http
from datetime import datetime
#import subprocess

from personalcapital import PersonalCapital, RequireTwoFactorException, TwoFactorVerificationModeEnum
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client import file, client, tools

from readsmscode import PushBulletSmsCodeReader

# go to script directory
os.chdir(os.path.dirname(os.path.realpath(__file__)))

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

for key in ['PC_PASSWORD', 'PB_ACCESS_KEY', 'GOOGLE_DRIVE_FOLDER']:
  if key not in os.environ:
    raise Exception('{0} is not defined'.format(key))

pc = PersonalCapital()

#email, password = "email@domain.tld", "password"
email = "andrew.macheret@gmail.com"
eprint("Email: {0}".format(email))
#password = getpass()
password = os.environ.get('PC_PASSWORD')
eprint("Password: {0}".format('*' * len(password)))

#proc = subprocess.Popen('node read-sms-code.js', stdout=subprocess.PIPE, shell=True)
pbAccessKey = os.environ.get('PB_ACCESS_KEY')
pb = PushBulletSmsCodeReader(pbAccessKey, r'^Your Personal Capital device authentication code is (\d+)\.$')
pb.start_watching()

try:
    pc.login(email, password)
except RequireTwoFactorException:
    pc.two_factor_challenge(TwoFactorVerificationModeEnum.SMS)
    #out, err = proc.communicate()
    #sms_code = out.rstrip().decode('utf-8')
    sms_code = pb.wait_for_sms_code()
    eprint("SMS Code: {0}".format(sms_code))
    pc.two_factor_authenticate(TwoFactorVerificationModeEnum.SMS, sms_code)
    pc.authenticate_password(password)

accounts_response = pc.fetch('/newaccount/getAccounts2')
accounts_data = accounts_response.json()['spData']

eprint('Networth: {0}'.format(accounts_data['networth']))

accountIds = map(lambda x: x['userAccountId'], accounts_data['accounts'])

transactions_response = pc.fetch('/transaction/getUserTransactions')
transactions = transactions_response.json()['spData']

simplified_transactions = sorted(
  map(lambda x: {
    'accountName': x['accountName'],
    'amount': x['amount'],
    'originalDescription': x['originalDescription'],
    'transactionDate': x['transactionDate'],
    'transactionType': x['transactionType'],
    'status': x['status']
  }, transactions['transactions']),
  key=lambda x: (x['transactionDate'], x['accountName']),
  reverse=True
)

csv_filename = "transactions-{0}.csv".format(datetime.now().strftime("%Y-%m-%d"))
with open(csv_filename, 'w') as output:
  writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC, lineterminator='\n')
  writer.writerow([
    'Date',
    'Account',
    'Description',
    'Amount',
    'Type',
    'Status'
  ])
  for transaction in simplified_transactions:
    writer.writerow([
      transaction['transactionDate'],
      transaction['accountName'],
      transaction['originalDescription'],
      transaction['amount'],
      transaction['transactionType'],
      transaction['status']
    ])



## pip install --upgrade google-api-python-client oauth2client
## maybe: pip install --upgrade httplib2

SCOPES = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/spreadsheets'
]
store = file.Storage('token.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
auth = creds.authorize(Http())
drive_service = build('drive', 'v3', http=auth)
sheets_service = build('sheets', 'v4', http=auth)

folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER')
file_metadata = {
   'name': csv_filename,
   'parents': [folder_id],
   'mimeType': 'application/vnd.google-apps.spreadsheet'
}
media = MediaFileUpload(csv_filename, mimetype='text/csv', resumable=True)
file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
spreadsheet_id = file.get('id')
eprint('File ID: {0}'.format(spreadsheet_id))
eprint('URL: https://docs.google.com/spreadsheets/d/{0}/edit'.format(spreadsheet_id))


get_spreadsheet_response = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
sheet_id = get_spreadsheet_response['sheets'][0]['properties']['sheetId']

update_spreadsheet_request = {
  'requests': [
    {
      'updateSheetProperties': {
        'properties': {
          'sheetId': sheet_id,
          'gridProperties': { 'frozenRowCount': 1 }
        },
        'fields': 'gridProperties(frozenRowCount)'
      }
    },
    {
      'autoResizeDimensions': {
        'dimensions': {
          'sheetId': sheet_id,
          'dimension': 'COLUMNS',
          'startIndex': 0,
          'endIndex': 6
        }
      }
    },
    {
      'updateDimensionProperties': {
        'range': {
          'sheetId': sheet_id,
          'dimension': 'COLUMNS',
          'startIndex': 2,
          'endIndex': 3
        },
        'properties': {
          'pixelSize': 400
        },
        'fields': 'pixelSize'
      }
    },
    {
      'sortRange': {
        'range': {
          'sheetId': sheet_id,
          'startRowIndex': 1,
          'startColumnIndex': 0,
          'endColumnIndex': 6
        },
        'sortSpecs': [
          {
            'dimensionIndex': 1,
            'sortOrder': 'ASCENDING'
          },
          {
            'dimensionIndex': 0,
            'sortOrder': 'DESCENDING'
          }
        ]
      }
    }    
  ]
}
update_sheet_response = sheets_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=update_spreadsheet_request).execute()



