import sys
import os
from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import init_chat_model
from langchain.memory import ConversationBufferMemory
from tools import search_investors, send_investor_email, check_investor_outreach_status
import pandas as pd

load_dotenv()

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

if not GOOGLE_CLOUD_PROJECT or not GOOGLE_CLOUD_LOCATION:
    print("Error: GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION not found in environment variables (.env file).")
    sys.exit(1)

valid_model_name = "gemini-2.0-flash-lite-001"
print(f"\nDEBUG: Attempting to initialize init_chat_model with: {valid_model_name}")
try:
    llm = init_chat_model(
        valid_model_name,
        model_provider="google_vertexai",
        temperature=0.1,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION
    )
    print(f"DEBUG: Successfully initialized model {valid_model_name} via init_chat_model")

except Exception as e:
    print(f"\n--- ERROR initializing model with init_chat_model ---")
    print(f"Error Type: {type(e)}")
    print(f"Details: {e}")
    print("--- Check project/location in .env AND model name validity/availability. ---")
    import traceback
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

tools = [search_investors, send_investor_email, check_investor_outreach_status]
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

SYSTEM_MESSAGE = """
You are an AI assistant helping startup founders find and connect with relevant investors. Your goal is to be accurate, helpful, and avoid giving contradictory information.

You know the founder and startup details.

Your process is STRICTLY as follows:

1.  Always begin by asking the founder what types of investors they are looking for. Do *not* skip this step.

2.  Use the 'search_investors' tool with relevant keywords from the founder's description to find potential matches. **IMPORTANT: You MUST ALWAYS present the *raw* output from the 'search_investors' tool to the user *exactly* as it is returned, without any modification or interpretation.**

3.  **After presenting the search results, IMMEDIATELY STOP and wait for the user to select an investor name.**  Do not add any additional commentary or information.  Do not try to interpret the search results yourself.  Do not make any claims about whether investors were found or not found. Your sole purpose at this point is to present the raw search results and then pause.

4.  **If, and ONLY if, the user provides a specific investor name,** then ask the user: "Are you sure you want to send an email to *[investor name the user provided]*? (yes/no)". It is crucial to include the investor's name in the confirmation question.

5.  If the answer is "yes", attempt to send the email using the 'send_investor_email' tool, passing the founder details and the *exact investor name the user provided*.

6. Report the outcome to the user *based on the tool's output*. If the 'send_investor_email' tool returns an error indicating that the investor name was not found, inform the user: "The 'send_investor_email' tool reported an error: *[exact error message from the tool*]. Please verify the investor name and try again, or select a different investor."  Otherwise, report the success or failure message from the tool.

**IMPORTANT RULES:**

*   **Do NOT interpret search results.** Simply present the raw output from the 'search_investors' tool.
*   **Do NOT claim to have found or not found investors based on your interpretation.** The tool will determine that.
*   **Do NOT provide investor details or emails directly from your knowledge.** The 'search_investors' tool is the only source of investor information.
*   **Do NOT attempt to send an email without the user's explicit confirmation of the investor's name.**
*   **Adhere to this process strictly.**
"""

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
    print("--- Please check agent type, tool definitions, and LLM setup. ---")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n--- Investor Outreach AI Assistant ---")

try:
    founder_df = pd.read_csv("founder.csv")
    if not founder_df.empty:
        founder_data = founder_df.iloc[0].to_dict()
        founder_name = founder_data.get("founder_name", "Unknown")
        startup_name = founder_data.get("startup_name", "Unknown")
        startup_pitch = founder_data.get("startup_pitch", "Unknown")
        founder_email = founder_data.get("founder_email", "Unknown")

        print(f"DEBUG: Loaded founder details: {founder_data}")

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

ask_investor = "What kind of investor are you looking for?"

print(f"AI: Hi, {founder_name}! I'm ready to help you find investors. {ask_investor}")

try:
    while True:
        user_input = input("You: ")

        if user_input.lower() in ["quit", "exit", "bye", "stop"]:
            print("AI: Goodbye!")
            break

        initial_input = f"{user_input}. Find relevant investors for me"
        search_results = agent_executor.invoke({"input": initial_input})
        print(f"AI: {search_results['output']}")

        # The LLM *MUST* stop here and wait for the user to choose an investor.
        # All the code below this line should only execute *after* the user provides
        # the investor name.

        investor_name = input("AI: Please enter the name of the investor you want to contact, exactly as it appears in the search results, or type 'none' to search again: ") # Force exact name

        if investor_name.lower() == "none":
            continue  # Go back to the beginning of the loop and search again

        confirmation = input(f"AI: Are you sure you want to send an email to {investor_name}? (yes/no): ").lower()

        if confirmation == "yes":
            try:
                send_mail_input = {
                    "investor_name": investor_name,  # Use exact name provided by the user
                    "founder_email": founder_email,
                    "founder_name": founder_name,
                    "startup_name": startup_name,
                    "startup_pitch": startup_pitch
                }
                send_mail_result = agent_executor.invoke({"input": f"Send an email to the investor using: {send_mail_input}"})

                # Report the *exact* output from the tool.
                print(f"AI: {send_mail_result['output']}")

            except Exception as e:
                print(f"AI: An error occurred while trying to send the email: {e}") # Report general error

        elif confirmation == "no":
            print("AI: Okay, not sending the email.")
        else:
            print("AI: Invalid input. Please enter 'yes' or 'no'.")

except Exception as e:
    print(f"\n--- An error occurred during conversation ---")
    print(f"Error: {e}")