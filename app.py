from flask import Flask, request
import jwt
from database import update_investor_acceptance, get_details_by_investor_email
from config import ACCEPT_LINK_SECRET_KEY, MAIL_FROM_ADDRESS, MAIL_FROM_NAME, MAIL_USERNAME, MAIL_PASSWORD, MAIL_HOST, MAIL_PORT, MAIL_ENCRYPTION#Import mail config
from send_cc_email import send_cc
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

app = Flask(__name__)

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
    app.run(debug=True, port=5000) 