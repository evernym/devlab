import os
import json

import boto3

def write_to_db(artist, album, table_name, region, dynamodb):
    print("Opening table: {}".format(table_name))
    table = dynamodb.Table(table_name)
    response = table.put_item(
        Item = {
            'Artist': artist,
            'Album': album
        }
    )
    return response

def lambda_handler(event, context):
    response = {
        "statusCode": 200,
        "body": ""
    }
    #print("event: {}".format(json.dumps(event, indent=4)))

    table = os.environ.get('DDB_TABLE_NAME')
    region = os.environ.get('REGION')

    if not 'localhost' in event['headers'].get('Host', None):
        dynamodb = boto3.resource('dynamodb', region_name=region)
    else:
        dynamodb = boto3.resource('dynamodb', region_name=region, endpoint_url="http://dynamodb-devlab:8000")

    write_args = {
        'artist': "Billy's Foo Band",
        'album': "Bar Baz",
        'table_name': table,
        'region': region,
        'dynamodb': dynamodb
    }

    write_response = write_to_db(**write_args)

    response['body'] = json.dumps({
        "message": "Hey there! I wrote: Artist: {artist}, Album: {album} to the dynamodb table: {table_name} in region: {region}! Response: {response}".format(**write_args, response=write_response)
    })

    return response

