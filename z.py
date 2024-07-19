import tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog, font, messagebox
import PyPDF2
import requests
import json
from requests.exceptions import ConnectionError, Timeout, RequestException
import threading
import subprocess

class PDFChatApp:
    def __init__(self, master):
        self.master = master
        master.title("Enhanced PDF Chat Application")

        # Set default font size
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=12)
        text_font = font.Font(family="TkFixedFont", size=12)

        self.timeout = 600  # Default timeout in seconds
        self.model = "Einstein-v7-Qwen2-7B-Q6_K.gguf:latest"  # Default model
        self.ollama_url = "http://localhost:11434/api/generate"

        # PDF loading section
        self.load_button = tk.Button(master, text="Load PDF", command=self.load_pdf)
        self.load_button.pack(pady=5)

        self.pdf_label = tk.Label(master, text="No PDF loaded")
        self.pdf_label.pack(pady=5)

        # Chat interface
        self.chat_history = scrolledtext.ScrolledText(master, state='disabled', height=15, font=text_font)
        self.chat_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.user_input = tk.Entry(master, width=50, font=text_font)
        self.user_input.pack(padx=10, pady=5, fill=tk.X)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(master, text="Send", command=self.send_message)
        self.send_button.pack(pady=5)

        # Settings buttons
        self.settings_frame = tk.Frame(master)
        self.settings_frame.pack(pady=5)

        self.change_timeout_button = tk.Button(self.settings_frame, text="Change Timeout", command=self.change_timeout)
        self.change_timeout_button.pack(side=tk.LEFT, padx=5)

        self.change_model_button = tk.Button(self.settings_frame, text="Change Model", command=self.change_model)
        self.change_model_button.pack(side=tk.LEFT, padx=5)

        self.check_ollama_button = tk.Button(self.settings_frame, text="Check Ollama", command=self.check_ollama_status)
        self.check_ollama_button.pack(side=tk.LEFT, padx=5)

        self.change_url_button = tk.Button(self.settings_frame, text="Change Ollama URL", command=self.change_ollama_url)
        self.change_url_button.pack(side=tk.LEFT, padx=5)

        self.start_ollama_button = tk.Button(self.settings_frame, text="Start Ollama", command=self.start_ollama)
        self.start_ollama_button.pack(side=tk.LEFT, padx=5)

        self.pdf_text = ""
        self.pdf_summary = ""

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            try:
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    self.pdf_text = ""
                    for page in reader.pages:
                        self.pdf_text += page.extract_text()
                self.pdf_label.config(text=f"Loaded: {file_path}")
                self.update_chat_history("System: PDF loaded successfully. Generating summary...")
                self.generate_summary()
            except Exception as e:
                self.update_chat_history(f"System Error: Failed to load PDF. Error: {str(e)}")

    def generate_summary(self):
        prompt = f"Please provide a brief summary of the following text:\n\n{self.pdf_text[:2000]}..."
        try:
            response = requests.post(self.ollama_url, 
                                     json={
                                         "model": self.model,
                                         "prompt": prompt,
                                         "stream": False
                                     },
                                     timeout=self.timeout)
            response.raise_for_status()
            self.pdf_summary = response.json().get('response', 'Failed to generate summary.')
            self.update_chat_history(f"System: PDF Summary:\n{self.pdf_summary}\n\nYou can now ask questions about the PDF.")
        except Exception as e:
            self.update_chat_history(f"System Error: Failed to generate summary. Error: {str(e)}")
            self.update_chat_history("Please check Ollama status and settings.")

    def send_message(self, event=None):
        user_message = self.user_input.get()
        if not user_message.strip():
            return
        self.update_chat_history(f"You: {user_message}")
        self.user_input.delete(0, tk.END)

        if not self.pdf_text:
            self.update_chat_history("System: Please load a PDF before asking questions.")
            return

        prompt = f"Context: {self.pdf_summary}\n\nFull Text: {self.pdf_text[:1000]}...\n\nHuman: {user_message}\n\nAssistant:"
        threading.Thread(target=self.fetch_response, args=(prompt,)).start()

    def fetch_response(self, prompt):
        try:
            response = requests.post(self.ollama_url, 
                                     json={
                                         "model": self.model,
                                         "prompt": prompt,
                                         "stream": False
                                     },
                                     timeout=self.timeout)
            response.raise_for_status()
            model_response = response.json().get('response', 'No response from the model.')
            self.update_chat_history(f"Assistant: {model_response}")
        except ConnectionError:
            self.update_chat_history(f"System Error: Cannot connect to Ollama at {self.ollama_url}. Please check Ollama status and settings.")
        except Timeout:
            self.update_chat_history(f"System Error: Request to Ollama timed out after {self.timeout} seconds. You can try increasing the timeout in settings.")
        except RequestException as e:
            self.update_chat_history(f"System Error: An error occurred. Error: {str(e)}")
            self.update_chat_history(f"Details: URL: {self.ollama_url}, Model: {self.model}, Timeout: {self.timeout}")

    def update_chat_history(self, message):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, message + "\n\n")
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)

    def change_timeout(self):
        new_timeout = simpledialog.askinteger("Timeout", f"Enter new timeout in seconds (current: {self.timeout}s):", 
                                              minvalue=1, maxvalue=300)
        if new_timeout:
            self.timeout = new_timeout
            self.update_chat_history(f"System: Timeout changed to {self.timeout} seconds.")

    def change_model(self):
        new_model = simpledialog.askstring("Model", f"Enter the model name (current: {self.model}):")
        if new_model:
            self.model = new_model
            self.update_chat_history(f"System: Model changed to {self.model}.")

    def check_ollama_status(self):
        try:
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                self.update_chat_history(f"Ollama is running. Available models: {', '.join(models)}")
            else:
                self.update_chat_history(f"Ollama responded with status code: {response.status_code}")
        except RequestException as e:
            self.update_chat_history(f"Failed to connect to Ollama: {str(e)}")
            self.update_chat_history("Please make sure Ollama is running and the URL is correct.")

    def change_ollama_url(self):
        new_url = simpledialog.askstring("Ollama URL", f"Enter new Ollama URL (current: {self.ollama_url}):")
        if new_url:
            self.ollama_url = new_url
            self.update_chat_history(f"System: Ollama URL changed to {self.ollama_url}")

    def start_ollama(self):
        try:
            subprocess.Popen(["ollama", "run", self.model])
            self.update_chat_history(f"System: Attempting to start Ollama with model {self.model}...")
        except Exception as e:
            self.update_chat_history(f"System Error: Failed to start Ollama. Error: {str(e)}")
            self.update_chat_history("Please make sure Ollama is installed and accessible from the command line.")

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFChatApp(root)
    root.mainloop()
