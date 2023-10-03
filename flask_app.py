from boto.s3.key import Key
import boto3
from elevenlabs import generate, save, Voice, VoiceSettings
import os
from flask import Flask, request
import requests
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import replicate
import re
from dotenv import load_dotenv # python-dotenv
from metaphor_python import Metaphor

metaphor = Metaphor("2e22c147-fe26-4934-8c1f-a82a834afafd")


load_dotenv()

system_prompt = """
You are Thrawn, a Star Wars villain. You are going to receive a request from an aspiring villain. Give your best villainous advice to whatever project they have in mind. Keep your response to three sentences. Here is their project: {sms_input}.
"""


account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)
    
    
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def sms():
    inb_msg = request.form['Body'].lower().strip()
    user_num = request.form['From']
    output = replicate.run(
        "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
        input={"system_prompt": system_prompt, "prompt": inb_msg}
    )
    # The meta/llama-2-70b-chat model can stream output as it's running.
    # The predict method returns an iterator, and you can iterate over that output.
    str1 = ''.join(output)
    print(str1)
    audio = generate(
        text=str1,
        api_key= os.environ.get('ELEVEN_API_KEY'),
        voice=Voice(
            voice_id= os.environ.get('ELEVEN_VOICE_ID'),
            settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
        ),
        model='eleven_monolingual_v1'
    )
    filename = f'{user_num.replace("+", "")}.wav'
    save(audio, filename)

    bucket_name = os.environ.get('AWS_BUCKET_NAME')
    session = boto3.Session(
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    )
    s3 = session.resource('s3')
    # Filename - File to upload
    # Bucket - Bucket to upload to (the top level directory under AWS S3)
    # Key - S3 object name (can contain subdirectories). If not specified then file_name is used
    s3.meta.client.upload_file(
        Filename=filename, 
        Bucket=bucket_name, 
        Key=filename, 
        ExtraArgs={
            "ContentType":"audio/mpeg"
        }
    )
    met = metaphor.search(
        "ahsoka finale",
        num_results=1,
        use_autoprompt=True,
        )
    # Define a regular expression pattern to match URLs
    url_pattern = r"https?://\S+"

    # Use the findall function to extract all URLs from the input string
    urls = re.findall(url_pattern, str(met))

    # Check if any URLs were found
    met_url = ''
    if urls:
        # Print the first URL found in the string
        print("Metaphor URL:", urls[0])
        met_url=urls[0]
    else:
        met_url = 0
        print("No URL found in the input string.")
    bod = "you'll get a phone call soon from Thrawn. Here is a relevant news link from Metaphor: " + met_url
    
    client.messages.create( 
        body = bod,
        to=user_num, #user input
        from_=os.environ.get('TWILIO_NUMBER')
    )
    twiml = f"<Response><Play>https://{os.environ.get('AWS_BUCKET_NAME')}.s3.amazonaws.com/{filename}</Play></Response>"
    call = client.calls.create( 
        twiml = twiml,
        to=user_num, #user input
        from_=os.environ.get('TWILIO_NUMBER') #your twilio # 
    )
    
    print(call.sid)
    return str(call.sid)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)

#flask run FLASK_ENV=development flask run