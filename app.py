from flask import Flask, render_template, request, jsonify, Response
import os
import time
import random
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt', 'pdf'}

#Langchain
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.chains import LLMChain
# Requires: pip install langchain



#AI Model Setup
MODEL_NAME = "mistral"

def build_chain(temperature=0.8):
    """
    Build Langchain pipeline dynamically
    """
    llm = Ollama(model=MODEL_NAME,temperature=temperature)
    prompt_template = """
You are a professional fantasy game designer.

Generate creative game assets based on the request.

Request:
{user_prompt}

Rules:
- Make it creative
- Game ready
- Short but detailed
- If user asks for items include abilities
- If quests include objective and reward
- If names include description

Output format:

TITLE
Description
Abilities / Lore
"""
    prompt = PromptTemplate(input_variables=["user_prompt"], template=prompt_template)
    chain = LLMChain(llm=llm, prompt=prompt, output_parser=StrOutputParser())
    return chain

#Fallback Generator
def dummy_generate(prompt, seed=None):

    random.seed(seed or int(time.time()))

    samples = [
        {
            "output": """Dragon Name: Zyphorax

Description:
An ancient frost dragon feared across the northern kingdoms.

Ability:
Breath of Eternal Ice
"""
        },
        {
            "output": """Quest: The Shadow Crown

Objective:
Retrieve the lost crown from the haunted ruins.

Reward:
Legendary Sword + 200 Gold
"""
        },
        {
            "output": """Item: Blade of Ash

Description:
A sword forged in volcanic fire.

Ability:
Burn damage + Shadow strike
"""
        }
    ]

    return random.choice(samples)

#File Reading
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_txt_file(filepath):
    """Read text file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def read_pdf_file(filepath):
    """Read PDF file"""
    try:
        import PyPDF2
        text = ""
        with open(filepath, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    except ImportError:
        return "PyPDF2 not installed. Install with: pip install PyPDF2"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

#Route
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/aichat")
def aichat():
    return render_template("aichat.html")

@app.route("/api/generate", methods=["POST"])
def generate():

    data = request.get_json() or {}

    prompt = data.get("prompt", "")
    temperature = float(data.get("temperature", 0.8))
    seed = data.get("seed", None)
    file_content = data.get("file_content", "")
    
    # Combine file context with prompt
    if file_content:
        prompt = f"Using the following document:\n\n{file_content}\n\n{prompt}"

    def stream_response():
        try:
            # Create LLM with streaming
            llm = Ollama(model=MODEL_NAME, temperature=temperature)
            prompt_template = """You are a professional fantasy game designer.

Generate creative game assets based on the request.

Request:
{user_prompt}

Rules:
- Make it creative
- Game ready
- Short but detailed
- If user asks for items include abilities
- If quests include objective and reward
- If names include description

Output format:

TITLE
Description
Abilities / Lore"""
            prompt_obj = PromptTemplate(input_variables=["user_prompt"], template=prompt_template)
            
            # Try using invoke with response streaming
            try:
                full_response = llm.invoke(prompt_obj.format(user_prompt=prompt))
                # Stream character by character for typing effect
                for char in full_response:
                    if char:
                        yield json.dumps({"token": char, "type": "content"}) + "\n"
                        time.sleep(0.02)  # Delay for typing effect
            except Exception as inner_e:
                # Fallback to dummy generator
                fallback = dummy_generate(prompt, seed)
                output = fallback["output"]
                for char in output:
                    yield json.dumps({"token": char, "type": "content"}) + "\n"
                    time.sleep(0.02)
        
        except Exception as e:
            # Final fallback
            fallback = dummy_generate(prompt, seed)
            output = fallback["output"]
            for char in output:
                yield json.dumps({"token": char, "type": "content"}) + "\n"
                time.sleep(0.02)
        
        # Signal end of stream
        yield json.dumps({"type": "done"}) + "\n"

    return Response(stream_response(), mimetype='application/x-ndjson', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })

@app.route("/api/upload-file", methods=["POST"])
def upload_file():
    """Upload and read file (TXT or PDF)"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use TXT or PDF"}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file content
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext == 'pdf':
            content = read_pdf_file(filepath)
        else:  # txt
            content = read_txt_file(filepath)
        
        # Clean up
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            "success": True,
            "filename": filename,
            "content": content[:5000]  # Limit to 5000 chars to avoid huge payloads
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# RUN SERVER


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
    
