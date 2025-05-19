from flask import Flask, request, render_template, jsonify
import os
import sys
import traceback
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import init_chat_model
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from tools import search_investors, send_investor_email, check_investor_outreach_status
from database import update_investor_acceptance, get_details_by_investor_email
from config import ACCEPT_LINK_SECRET_KEY, MAIL_FROM_ADDRESS, MAIL_FROM_NAME, MAIL_USERNAME, MAIL_PASSWORD, MAIL_HOST, MAIL_PORT, MAIL_ENCRYPTION
from send_cc_email import send_cc
import jwt
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "your_secret_key")  # Set a secret key
csrf = CSRFProtect(app)
app.config['WTF_CSRF_ENABLED'] = True

load_dotenv()

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

if not GOOGLE_CLOUD_PROJECT or not GOOGLE_CLOUD_LOCATION:
    print("Error: GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION not found in environment variables (.env file).")
    sys.exit(1)

valid_model_name = "gemini-2.0-flash-lite-001"

llm = None  # Initialize llm outside the route
agent_executor = None  # Initialize agent_executor outside the route
founder_name = "Unknown" # Initialize
startup_name = "Unknown"
startup_pitch = "Unknown"
founder_email = "Unknown"

# Initialize LLM and agent globally (or within a function called once at startup)
def initialize_agent_and_llm():
    global llm, agent_executor, founder_name, startup_name, startup_pitch, founder_email
    try:
        llm = init_chat_model(
        valid_model_name,
        model_provider="google_vertexai",
        temperature=0.1,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION
    )
        print(f"DEBUG: Successfully initialized model {valid_model_name}")

    except Exception as e:
        print(f"\n--- ERROR initializing model ---")
        print(f"Error Type: {type(e)}")
        print(f"Details: {e}")
        print("--- Check project/location in .env AND model name validity/availability. ---")
        traceback.print_exc()
        sys.exit(1)

    print("\nDEBUG: Testing LLM connection...")
    try:
        test_response = llm.invoke(["Confirm you are ready."])
        print(f"DEBUG: LLM Test Response: {test_response}")
        print("DEBUG: LLM connection seems OK.")
    except Exception as llm_error:
        print(f"--- FATAL ERROR: Cannot connect to LLM! ---")
        print(f"--- ERROR DETAILS: {llm_error} ---")
        print("--- Please check GCP project permissions for Vertex AI for your account/service account. ---")
        sys.exit(1)

    # Load founder details from CSV *before* defining SYSTEM_MESSAGE
    try:
        founder_df = pd.read_csv("founder.csv")
        if not founder_df.empty:
            founder_data = founder_df.iloc[0].to_dict()
            founder_name = founder_data.get("founder_name", "Unknown")
            founder_email = founder_data.get("founder_email", "Unknown")
            startup_name = founder_data.get("startup_name", "Unknown")
            startup_pitch = founder_data.get("startup_pitch", "Unknown")

            print(f"DEBUG: Loaded founder details: {founder_data}")
            print(f"DEBUG: Loaded founder_name: {founder_name}")
            print(f"DEBUG: Loaded founder_email: {founder_email}")
            print(f"DEBUG: Loaded startup_name: {startup_name}")
            print(f"DEBUG: Loaded startup_pitch: {startup_pitch}")

        else:
            print("ERROR: founder.csv is empty!")
            founder_name = "Unknown"
            startup_name = "Unknown"
            startup_pitch = "Unknown"
            founder_email = "Unknown"

    except FileNotFoundError:
        print("ERROR: founder.csv not found!")
        founder_name = "Unknown"
        startup_name = "Unknown"
        startup_pitch = "Unknown"
        founder_email = "Unknown"
   
    tools = [
        Tool(
            name="search_investors",
            func=search_investors,
            description="useful for when you need to find investors. Input should be a search query."
        ),
         Tool(
            name="send_investor_email",
            func=send_investor_email,
            description="useful for when you need to send an email to an investor. The input should be ONLY the investor's name. Do not include any other information."
        ),
        Tool(
            name="check_investor_outreach_status",
            func=check_investor_outreach_status,
            description="useful for when you need to check the status of an investor outreach."
        )
    ]
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    SYSTEM_MESSAGE = f"""
    You are an AI assistant helping startup founders find and connect with relevant investors. Your goal is to be accurate and helpful.

    You know the following details about the founder and their startup:
    - Founder Name: {founder_name}
    - Founder Email: {founder_email}
    - Startup Name: {startup_name}
    - Startup Pitch: {startup_pitch}

    You MUST use the founder's details provided above in all interactions without asking the user to confirm or provide them again. These details are ALREADY KNOWN TO YOU and are DEFINITIVE. Do not ask the user for their details.
    
    Your process is STRICTLY as follows:

    1. Ask the founder what types of investors they are looking for. 

    2. Use the 'search_investors' tool with relevant keywords to find potential matches. Present the *raw* output from the 'search_investors' tool to the user *exactly* as it is returned.

    3.  **After presenting the search results, IMMEDIATELY STOP and wait for the user to select an investor name.**

    4.  **If, and ONLY if, the user provides a specific investor name,** ask the user: "Are you sure you want to send an email to *[investor name the user provided]*? (yes/no)". 

    5.  If the answer is "yes", attempt to send an email call the tool `send_investor_email` with the investor name: {investor_name}, founder email: {founder_email}, founder name: {founder_name}, startup name: {startup_name}, startup pitch: {startup_pitch}. You already know the founder and startup's details. Do not ask the user for them.

    6. Report the outcome to the user based on the tool's output.

    **IMPORTANT RULES:**

    *   Do NOT interpret search results. 
    *   Do NOT claim to have found or not found investors based on your interpretation. 
    *   Do NOT provide investor details or emails directly from your knowledge. The 'search_investors' tool is the only source of investor information.
    *   Do NOT attempt to send an email without the user's explicit confirmation of the investor's name.
    *   You MUST use the founder details already provided.
    """

    print(f"DEBUG: SYSTEM_MESSAGE: {SYSTEM_MESSAGE}")

    print("\nDEBUG: Initializing agent...")
    try:
        agent_executor = initialize_agent(
            tools,
            llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            memory=memory,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_message": SYSTEM_MESSAGE
            }
        )
        print("DEBUG: Agent initialized successfully!")

    except Exception as e:
        print(f"\n--- ERROR during agent initialization ---")
        print(f"Error Type: {type(e)}")
        print(f"Details: {e}")
        print("--- Check project type, tool definitions, and LLM setup. ---")
        traceback.print_exc()
        sys.exit(1)

    print("\n--- Investor Outreach AI Assistant ---")

initialize_agent_and_llm()

def send_confirmation_email(recipient_email: str, subject: str, body: str) -> bool:
    """Sends a confirmation email using SMTP configuration."""
    sender_login_email = MAIL_USERNAME
    sender_password = MAIL_PASSWORD
    sender_display_name = MAIL_FROM_NAME
    sender_from_address = MAIL_FROM_ADDRESS
    smtp_host = MAIL_HOST
    try:
        smtp_port = int(MAIL_PORT)
    except (ValueError, TypeError):
        print(f"Warning: Invalid MAIL_PORT '{MAIL_PORT}' in .env. Defaulting to 587.")
        smtp_port = 587
    use_tls = MAIL_ENCRYPTION and MAIL_ENCRYPTION.lower() == 'tls'

    message = MIMEText(body, 'html', 'utf-8')
    message['Subject'] = subject
    message['From'] = formataddr((sender_display_name or sender_from_address, sender_from_address))
    message['To'] = recipient_email

    server = None
    try:
        print(f"DEBUG: Attempting SMTP connection to {smtp_host}:{smtp_port}")
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            if use_tls or smtp_port == 587:
                print("DEBUG: Starting TLS...")
                server.starttls()
                server.ehlo()
                print("DEBUG: TLS Handshake successful.")

        print(f"DEBUG: Logging in as {sender_login_email}...")
        server.login(sender_login_email, sender_password)
        print(f"DEBUG: Login success")

        server.sendmail(sender_from_address, [recipient_email], message.as_string())
        print(f"DEBUG: Send Mail success")

        return True

    except Exception as e:
        print(f"Error sending confirmation email: {e}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

@app.route('/')
def index():
     ai_greeting = f"AI: Hi, {founder_name}! I'm ready to help you find investors."
     return render_template('index.html', ai_greeting=ai_greeting)

@app.route('/get_response', methods=['POST'])
@csrf.exempt
def get_response():
    global agent_executor, founder_name, startup_name, startup_pitch, founder_email
    user_message = request.form['user_message']

    try:
        if agent_executor is None:
            bot_response = "The agent is not initialized. Please try again later."
        else:
            initial_input = f"{user_message}."
            search_results = agent_executor.invoke({"input": initial_input})
            bot_response = f"AI: {search_results['output']}"

            if "Please enter the name of the investor you want to contact" in bot_response:
                investor_list_str = search_results['output'].split("Here are some potential investors:")[1].split("Please enter the name of the investor you want to contact")[0]
                investor_list = [item.strip() for item in investor_list_str.split(',')]
                return jsonify({
                    'bot_response': "Here are some potential investors:",
                    'investor_options': investor_list
                })
            elif "Are you sure you want to send an email to" in bot_response:
                return jsonify({'bot_response': bot_response})
            elif 'send_investor_email' in user_message:
                return jsonify({'bot_response': bot_response})

            else:
                bot_response =search_results['output']
                return jsonify({'bot_response': bot_response})

    except Exception as e:
        bot_response = f"Error: There is some error {e}"

    return jsonify({'bot_response': bot_response})

@app.route('/send_email_to_investor', methods=['POST'])
def send_email_to_investor():
    global agent_executor, founder_name, startup_name, startup_pitch, founder_email
    investor_name = request.form['investor_name']

    try:
        if agent_executor is None:
            return jsonify({'bot_response': "The agent is not initialized. Please try again later."})
        else:
            confirmation_message = f"Are you sure you want to send an email to {investor_name}? (yes/no)"
            return jsonify({'bot_response': confirmation_message, 'require_confirmation': True, 'investor_name': investor_name})

    except Exception as e:
        return jsonify({'bot_response': f"Error: {e}"})


@app.route('/confirm_send_email', methods=['POST'])
def confirm_send_email():
    global agent_executor, founder_name, startup_name, startup_pitch, founder_email
    confirmation = request.form['confirmation']
    investor_name = request.form['investor_name']

    if confirmation.lower() == 'yes':
        try:
            email_instructions = f"call the tool `send_investor_email` with the investor name: {investor_name}, founder email: {founder_email}, founder name: {founder_name}, startup name: {startup_name}, startup pitch: {startup_pitch}"
            bot_response = agent_executor.invoke({"input": email_instructions})
            return jsonify({'bot_response': bot_response['output']})
        except Exception as e:
            return jsonify({'bot_response': f"Error sending email: {e}"})
    else:
        return jsonify({'bot_response': "Email not sent."})


@app.route('/accept_investor')
def accept_investor():
    token = request.args.get('token')
    print(f"DEBUG: Received token: {token}")

    try:
        payload = jwt.decode(token, ACCEPT_LINK_SECRET_KEY, algorithms=["HS256"])
        print(f"DEBUG: JWT payload: {payload}")
        investor_email = payload['investor_email']
        founder_email = payload['founder_email']
        investor_name = payload.get("investor_name")
        founder_name = payload.get("founder_name")
        startup_name = payload.get("startup_name")

        accepted = update_investor_acceptance(investor_email)

        if accepted:
            investor_subject = "Confirmation: Interest in " + startup_name
            investor_body = f"""
            Dear {investor_name},

            This email confirms that you have expressed interest in learning more about {startup_name} and its founder, {founder_name}.

            We will be connecting you with {founder_name} shortly.
            """
            send_investor_confirmation = send_confirmation_email(investor_email, investor_subject, investor_body)
            if not send_investor_confirmation:
                return "Thank you! But the confirmation email not sent to the investor."

            founder_subject = f"{investor_name} is interested in {startup_name}!"
            founder_body = f"""
            Dear {founder_name},

            {investor_name} has expressed interest in learning more about {startup_name}.

            We have notified {investor_name} and will connect you both.
            """
            send_founder_confirmation = send_confirmation_email(founder_email, founder_subject, founder_body)

            if not send_founder_confirmation:
                 return "Thank you! But the confirmation email not sent to the founder."

            details = get_details_by_investor_email(investor_email)
            if details:
                send_cc_success = send_cc(details['founder_email'], investor_email, details['investor_name'], details['founder_name'], details['startup_name'])

                if send_cc_success:
                    return "Thank you! Both confirmation emails and connection emails are sent successfully!."
                else:
                    return "Thank you! Both confirmation emails are sent! But We encountred error while connecting to the founder."
            else:
                return "Thank you! Both confirmation emails are sent! But we encountred an error while fetching data"

        else:
            return "Invalid or expired link."

    except jwt.ExpiredSignatureError:
        return "Link expired."
    except jwt.InvalidTokenError:
        return "Invalid token."
    except Exception as e:
        print(f"Error processing acceptance: {e}")
        return f"An error occurred: {e}"

if __name__ == '__main__':

    app.run(debug=True, use_reloader=False)