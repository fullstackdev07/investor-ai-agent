def get_initial_outreach_email(investor_name: str, founder_name: str, founder_startup_name: str, startup_pitch: str, agent_name: str = "AI Assistant", investor_focus: str = "your area of interest", acceptance_link: str = "") -> dict:

    subject = f"Introduction: {founder_startup_name} - Exploring Investment Synergy"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Introduction: {founder_startup_name}</title>
    </head>
    <body>
        <p>Dear {investor_name},</p>
        <p>My name is {agent_name}, and I'm assisting {founder_name}, the founder of {founder_startup_name}.</p>
        <p>{founder_startup_name} is working on {startup_pitch}. We noted your interest in {investor_focus} and thought there might be a potential fit based on our data.</p>

        <p>Would you be open to a brief introductory call with {founder_name} to learn more?</p>

        <p><a href="{acceptance_link}" style="background-color:#4CAF50;border:none;color:white;padding:10px 20px;text-align:center;text-decoration:none;display:inline-block;font-size:16px;cursor:pointer;">I'm Interested</a></p>
        <p>Best regards,</p>
        <p>{founder_name}</p>
    </body>
    </html>
    """
    return {"subject": subject, "body": html_body.strip()}

def get_follow_up_cc_email(investor_name: str, founder_name: str, founder_startup_name: str, agent_name: str = "AI Assistant") -> dict:
    """ Formats the follow-up email to CC both parties. """
    subject = f"Re: Introduction: {founder_startup_name} - Connecting You Both"
    body = f"""
Great!

{investor_name} and {founder_name} - connecting you both as requested.

{founder_name}, {investor_name} has expressed interest in learning more. Please feel free to coordinate directly to find a suitable time.

Best regards,

{founder_name}
"""
    return {"subject": subject, "body": body.strip()}
