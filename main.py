import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from queue import Queue
import threading
import json
import os
from datetime import datetime


class WellbeingAssistant:
    def __init__(self, api_key):
        # Initialize Speech Recognition
        self.recognizer = sr.Recognizer()

        # Initialize Text-to-Speech
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)

        # Initialize Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

        # Set up chat context and history
        self.chat_history = []
        self.response_queue = Queue()

        # Define the initial context for the AI
        self.system_prompt = """
        You are a supportive mental wellbeing assistant. Your responses should be:
        - Empathetic and understanding
        - Brief and clear (keep responses under 3 sentences when possible)
        - Non-judgmental and encouraging
        - Professional (never diagnose or give medical advice)
        - Safety-conscious (refer to professional help when needed)

        If you detect signs of crisis, always provide these emergency resources:
        - National Crisis Hotline: 988
        - Crisis Text Line: Text HOME to 741741
        """

    def transcribe_audio(self):
        """Capture and transcribe audio from microphone"""
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio)
                return text
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                print("Could not request results; check your network connection")
                return None

    def generate_response(self, user_input):
        """Generate response using Gemini"""
        # Combine system prompt with chat history
        full_context = self.system_prompt + "\n\nPrevious conversation:\n" + \
                       "\n".join([f"User: {h['user']}\nAssistant: {h['assistant']}"
                                  for h in self.chat_history[-3:]])

        try:
            response = self.model.generate_content(
                [full_context, f"User: {user_input}"]
            )
            return response.text
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm sorry, I'm having trouble processing that right now. Could you please try again?"

    def speak_response(self, text):
        """Convert text to speech"""
        self.engine.say(text)
        self.engine.runAndWait()

    def save_conversation(self):
        """Save conversation history to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(self.chat_history, f, indent=4)

    def run(self):
        """Main loop for the assistant"""
        print("Wellbeing Assistant is ready! Speak naturally or type 'quit' to exit.")

        while True:
            # Get user input
            user_input = self.transcribe_audio()

            if user_input:
                print(f"You said: {user_input}")

                # Check for quit command
                if user_input.lower() == 'quit':
                    print("Saving conversation and exiting...")
                    self.save_conversation()
                    break

                # Generate and speak response
                response = self.generate_response(user_input)
                print(f"Assistant: {response}")

                # Store in chat history
                self.chat_history.append({
                    "user": user_input,
                    "assistant": response,
                    "timestamp": datetime.now().isoformat()
                })

                # Speak response
                self.speak_response(response)


if __name__ == "__main__":
    # Replace with your Gemini API key
    API_KEY = "AIzaSyDh6ZVmYmATOvv-xfdHKc_njOlX4U_pxLU"

    assistant = WellbeingAssistant(API_KEY)
    assistant.run()