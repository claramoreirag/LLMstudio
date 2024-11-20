import boto3
import os
from datetime import datetime
import uuid


client = boto3.client('license-manager', region_name='us-east-1')

def checkoutLic():
    try:
        response = client.checkout_license(
            ProductSKU=os.environ["PROD_ID"],
            CheckoutType='PROVISIONAL',
            KeyFingerprint=os.environ["ISSUER_FT"],
            Entitlements=[
                {
                    'Name': 'API_free',
                    'Unit': 'None'
                },
                {
                    'Name': 'API_month',
                    'Unit': 'None'
                },
            ],
            ClientToken=str(uuid.uuid4())
        )
        if len(response['EntitlementsAllowed']) > 0 and (response['EntitlementsAllowed'][0]['Value']=='Enabled' or response['EntitlementsAllowed'][1]['Value']=='Enabled'):
            return True
        else:
            print('Insufficient or expired license')
            return False
    except Exception as e:
        print("Error could not call LM checkout api **" + str(e))
        return False
