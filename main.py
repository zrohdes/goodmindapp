import speech_recognition as sr
import google.generativeai as genai
import os
import platform
import subprocess
import tempfile
import json
from datetime import datetime
import threading
import streamlit as st
import time
from queue import Queue

# Replace with your actual Gemini API key
API_KEY = "AIzaSyDh6ZVmYmATOvv-xfdHKc_njOlX4U_pxLU"


class VoiceAssistant:
    def __init__(self, api_key):
        # Initialize Speech Recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.4  # Even faster response
        self.recognizer.non_speaking_duration = 0.2

        # Initialize Gemini with caching
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 150,  # Limit token count for faster responses
        }
        self.model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

        # Chat history
        self.chat_history = []

        # Status tracking
        self.status = "Ready"
        self.current_user_text = ""
        self.current_assistant_text = ""

        # Flags for UI
        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        self.running = True

        # Message queue for UI updates
        self.message_queue = Queue()

        # System prompt (shortened for faster processing)
        self.system_prompt = """
        You are a brief, empathetic mental health assistant. Keep responses under 3 sentences. Never diagnose. If crisis detected, provide: Crisis Hotline: 988, Text: HOME to 741741.
        """

    def speak(self, text):
        """Convert text to speech with less blocking"""
        self.is_speaking = True
        self.status = "Speaking..."
        self.current_assistant_text = text

        # Add to message queue for UI update
        self.message_queue.put(("assistant", text))

        def speak_thread():
            try:
                system = platform.system()
                if system == "Windows":
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.ps1') as script_file:
                        script_path = script_file.name
                        escaped_text = text.replace("'", "''")
                        ps_script = f'Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Rate = 1; $speak.Speak(\'{escaped_text}\');'
                        script_file.write(ps_script.encode('utf-8'))

                    subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path],
                                   shell=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        os.unlink(script_path)
                    except:
                        pass

                elif system == "Darwin":  # macOS
                    escaped_text = text.replace('"', '\\"')
                    os.system(f'say -r 220 "{escaped_text}"')  # Faster rate

                elif system == "Linux":
                    escaped_text = text.replace('"', '\\"')
                    os.system(f'espeak -s 150 "{escaped_text}"')  # Faster rate

                self.is_speaking = False
                self.status = "Ready"
            except Exception as e:
                self.status = f"TTS error: {e}"
                self.is_speaking = False

        # Run speech in separate thread to avoid blocking
        threading.Thread(target=speak_thread, daemon=True).start()

    def listen(self):
        """Listen for speech with minimal blocking"""
        self.is_listening = True
        self.status = "Listening..."
        self.current_user_text = ""

        try:
            with sr.Microphone() as source:
                # Quick ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                # Short phrase time limit for quicker responses
                audio = self.recognizer.listen(source, phrase_time_limit=10)

                try:
                    self.status = "Processing speech..."
                    text = self.recognizer.recognize_google(audio)
                    self.current_user_text = text

                    # Add to message queue for UI update
                    self.message_queue.put(("user", text))

                    self.is_listening = False
                    return text
                except sr.UnknownValueError:
                    self.status = "Could not understand audio"
                    self.is_listening = False
                    return None
                except sr.RequestError as e:
                    self.status = f"Recognition error: {e}"
                    self.is_listening = False
                    return None

        except Exception as e:
            self.status = f"Listening error: {e}"
            self.is_listening = False
            return None

    def generate_response(self, user_input):
        """Generate more efficient responses"""
        # Use a minimal context window for faster processing
        recent_history = ""
        if self.chat_history:
            # Only include the last exchange
            last_exchange = self.chat_history[-1]
            recent_history = f"User: {last_exchange['user']}\nAssistant: {last_exchange['assistant']}\n"

        prompt = f"{self.system_prompt}\n\nRecent: {recent_history}\nUser: {user_input}"

        try:
            # Using streaming response for faster first token
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            self.status = f"Generation error: {e}"
            return "I'm having trouble right now. Can you try again?"

    def process_input(self, user_input):
        """Process user input more efficiently"""
        self.is_processing = True
        self.status = "Generating response..."

        # Generate response
        response = self.generate_response(user_input)

        # Add to chat history
        self.chat_history.append({
            "user": user_input,
            "assistant": response,
            "timestamp": datetime.now().isoformat()
        })

        # Speak the response
        self.speak(response)

        self.is_processing = False

    def save_conversation(self):
        """Save conversation to file"""
        if not self.chat_history:
            self.status = "No conversation to save"
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(self.chat_history, f, indent=4)

        self.status = f"Conversation saved: {filename}"
        return filename

    def run_listening_loop(self):
        """Run the listening loop in a separate thread"""
        while self.running:
            # Only listen when not busy with other tasks
            if not self.is_processing and not self.is_speaking:
                user_input = self.listen()

                if user_input:
                    # Check for exit commands
                    if user_input.lower() in ["goodbye", "exit", "quit", "bye"]:
                        self.speak("Goodbye! Have a great day.")
                        self.running = False
                        break

                    # Check for save command
                    elif user_input.lower() == "save conversation":
                        filename = self.save_conversation()
                        if filename:
                            self.speak("Conversation saved.")
                        else:
                            self.speak("No conversation to save yet.")

                    # Process normal input
                    else:
                        threading.Thread(target=self.process_input, args=(user_input,), daemon=True).start()

            # Small sleep to prevent CPU spinning
            time.sleep(0.05)

    def start(self):
        """Start the assistant"""
        self.running = True
        threading.Thread(target=self.run_listening_loop, daemon=True).start()
        self.speak("Hello, I'm your wellness assistant. How can I help you today?")

    def stop(self):
        """Stop the assistant"""
        self.running = False
        self.status = "Stopped"


# Streamlit app with improved performance
def main():
    st.set_page_config(
        page_title="Voice Wellness Assistant",
        page_icon="🎤",
        layout="centered"
    )

    st.title("Voice Wellness Assistant")

    # Initialize session state
    if 'initialized' not in st.session_state:
        st.session_state.assistant = VoiceAssistant(API_KEY)
        st.session_state.running = False
        st.session_state.messages = []
        st.session_state.initialized = True

    # Control buttons in columns for better layout
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Start Assistant", key="start", disabled=st.session_state.running):
            st.session_state.running = True
            st.session_state.assistant.start()
            st.rerun()

    with col2:
        if st.button("Stop Assistant", key="stop", disabled=not st.session_state.running):
            st.session_state.running = False
            st.session_state.assistant.stop()
            st.rerun()

    with col3:
        if st.button("Save Conversation", key="save"):
            filename = st.session_state.assistant.save_conversation()
            if filename:
                st.success(f"Conversation saved to {filename}")
            else:
                st.warning("No conversation to save")

    # Status indicator
    status_indicator = st.empty()

    # Display conversation in chat-like format
    chat_container = st.container()

    # Function to update status
    def update_status():
        assistant = st.session_state.assistant

        if assistant.is_listening:
            status_color = "#FF5733"  # Red
            status_text = "Listening..."
        elif assistant.is_speaking:
            status_color = "#33FF57"  # Green
            status_text = "Speaking..."
        elif assistant.is_processing:
            status_color = "#3357FF"  # Blue
            status_text = "Processing..."
        else:
            status_color = "#AAAAAA"  # Gray
            status_text = "Ready"

        status_indicator.markdown(f"""
        <div style="display: flex; align-items: center; margin: 20px 0;">
            <div style="width: 15px; height: 15px; border-radius: 50%; background-color: {status_color}; margin-right: 10px;"></div>
            <span style="font-size: 18px; font-weight: bold;">{status_text}</span>
            <span style="margin-left: 10px; color: #666; font-size: 14px;">{assistant.status}</span>
        </div>
        """, unsafe_allow_html=True)

    # Function to update messages from queue
    def update_messages():
        assistant = st.session_state.assistant

        # Process any new messages from the queue
        while not assistant.message_queue.empty():
            msg_type, msg_text = assistant.message_queue.get()
            st.session_state.messages.append({"role": msg_type, "content": msg_text})

        # Display all messages
        with chat_container:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(
                        f"<div style='background-color: #E8E8E8; padding: 10px; border-radius: 10px; margin: 5px 0;'><strong>You:</strong> {msg['content']}</div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='background-color: #D1F0FF; padding: 10px; border-radius: 10px; margin: 5px 0;'><strong>Assistant:</strong> {msg['content']}</div>",
                        unsafe_allow_html=True)

    # Add an info section
    with st.expander("How to use"):
        st.write("""
        1. Click 'Start Assistant' to begin
        2. Speak clearly when the status is 'Listening...'
        3. Wait for the assistant to respond
        4. Say 'goodbye' or 'exit' to end the session
        5. Say 'save conversation' to save the chat history
        """)

    # Simple function to refresh UI
    def refresh_ui():
        update_status()
        update_messages()
        time.sleep(0.1)
        st.rerun()

    # Keep the UI refreshed
    refresh_ui()


if __name__ == "__main__":
    main()