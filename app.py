from boto.s3.key import Key
import boto3
from elevenlabs import generate, save, Voice, VoiceSettings
import os
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms import Replicate
from langchain.memory import ConversationBufferWindowMemory
from flask import Flask, request
import requests
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import replicate
from dotenv import load_dotenv # python-dotenv


load_dotenv()

template = """Assistant is a large language model.

Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. As a language model, Assistant is able to generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.

Assistant is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Assistant is able to generate its own text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on a wide range of topics.

Overall, Assistant is a powerful tool that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. Whether you need help with a specific question or just want to have a conversation about a particular topic, Assistant is here to assist. 

I want you to pretend you are Thrawn and give advice and answer questions as he would. You will reply with a paragraph containing answers and no questions as he would respond to {sms_input}.
Assistant:"""

prompt = PromptTemplate(input_variables=["sms_input"], template=template)
sms_chain = LLMChain(
    llm = Replicate(model="a16z-infra/llama13b-v2-chat:df7690f1994d94e96ad9d568eac121aecf50684a0b0963b25a41cc40061269e5"), 
    prompt=prompt,
    memory=ConversationBufferWindowMemory(k=2),
    llm_kwargs={"max_length": 4096}
)
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)
    
    
app = Flask(__name__)


@app.route('/sms', methods=['GET', 'POST'])
def sms():
    inb_msg = request.form['Body'].lower().strip()
    user_num = request.form['From']
    resp = MessagingResponse()
    output = sms_chain.predict(sms_input=inb_msg)
    print(output)
    audio = generate(
        text=str(output),
        api_key= os.environ.get('ELEVEN_API_KEY'),
        voice=Voice(
            voice_id= os.environ.get('ELEVEN_VOICE_ID'),
            settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
        ),
        model='eleven_monolingual_v1'
    )
    save(audio, 'thrawn.wav')

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
        Filename='thrawn.wav', 
        Bucket=bucket_name, 
        Key='thrawn.wav', 
        ExtraArgs={
            "ContentType":"audio/mpeg"
        }
    )
    
    client.messages.create( 
        body = "you'll get a phone call soon from Thrawn",
        to=user_num, #user input
        from_=os.environ.get('TWILIO_NUMBER')
    )
    twiml = f"<Response><Play>https://{os.environ.get('AWS_BUCKET_NAME')}.s3.amazonaws.com/thrawn.wav</Play></Response>"
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