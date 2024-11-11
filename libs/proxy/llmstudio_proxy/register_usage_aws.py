import boto3
import os

client = boto3.client('meteringmarketplace', region_name='us-east-1')

def registerUsage():
    try:
        response = client.register_usage(
            ProductCode="7d25fgis4ph4jqywofjybfr2r",
            PublicKeyVersion=1
        )
        print('Response from RegisterUsage API call ' + str(response))
        return True
    except Exception as e:
        print("Error: could not call register_usage API **" + str(e))
        return False