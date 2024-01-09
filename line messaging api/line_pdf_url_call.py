#lineのユーザIDを入力として受け取って、そのユーザIDがファイル名に含まれたPDFをs3上で探して、そのURLを返すaws lambda関数
import boto3
import os

def lambda_handler(event, context):
    # Extract the LINE user ID from the event object
    line_user_id = event.get('line_user_id')
    
    if not line_user_id:
        return {'statusCode': 400, 'body': 'LINE user ID not provided'}
    
    # Initialize a boto3 client for S3
    s3_client = boto3.client('s3')
    bucket_name = os.environ['BUCKET_NAME']  # Set your bucket name in Lambda's environment variables

    try:
        # List objects in the specified S3 bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' in response:
            for item in response['Contents']:
                file_name = item['Key']
                
                # Check if the file name contains the LINE user ID and is a PDF
                if line_user_id in file_name and file_name.endswith('.pdf'):
                    file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
                    return {'statusCode': 200, 'body': file_url}
        
        # No matching file found
        return {'statusCode': 404, 'body': 'No matching PDF file found'}

    except Exception as e:
        return {'statusCode': 500, 'body': f'Error occurred: {str(e)}'}

# Example event for testing
event = {'line_user_id': '1234567890'}
print(lambda_handler(event, None))
