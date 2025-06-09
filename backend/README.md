# Introduction 
Backend API for GenAssist

# Getting Started
Create virtual environment and install requirements\


0. Install python and pip (if running on a clean linux machine)

    sudo apt-get update
    sudo apt-get install software-properties-common
    apt-get install build-essential
    sudo apt-get update; sudo apt-get install make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev ffmpeg
    
    install pyenv: `curl -fsSL https://pyenv.run | bash`
    pyenv install 3.10

    *Container toolkit (if needed):
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit


1. Install the required dependencies:
    ```bash
    Mac/Linux:
    python3.10 -m venv genassist_env
    source genassist_env/bin/activate

    ```

2. Install the required dependencies:
    ```bash
    python -m pip install --upgrade pip==24.0
    pip install -r requirements.txt
    ```

    create .env file from example and put config values

    If using HF model for the first time, go to https://hf.co/pyannote/segmentation to accept license agreeement

3. Start db and redis locally:
    ```bash
    docker compose up -d db redis
    ```

3. Run in debug mode:
    ```bash
    python run.py
    ```
    
4. Try out APIs using Swagger UI:
    API key: test123
    UserRead Auth: admin/genadmin
    ```
    http://localhost:8000/docs
    ```

5. Lint:
    ```bash
    pylint app
    ```

6. Run tests:
    ```bash
    pytest .
    ```

7. Debug:
    Run vscode debug on the main file "run.py"
    Make sure the correct Python interpreter is selected (pointing to the genassist_env environment)

8. Exit:
    ```bash
    deactivate
    ```

9. Buid and run docker image:
    ```bash
    docker build -f './Dockerfile' -t ritech/genassist-dev .
    docker run ritech/genassist-$(echo "$(Build.BuildNumber)" | sed 's/\+/-/g') --expose $(APIPORT)
    ```