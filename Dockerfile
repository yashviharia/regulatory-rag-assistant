# Hugging Face Spaces (Docker SDK) image for the Streamlit app.
# The index and embedding model are built into the image so the Space
# starts answering immediately; GROQ_API_KEY comes from a Space secret.
FROM python:3.12-slim

# Spaces run containers as uid 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface ANONYMIZED_TELEMETRY=False
WORKDIR /home/user/app

# CPU-only torch keeps the image a few GB smaller than the default CUDA build
RUN pip install --no-cache-dir --user torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .
RUN python src/ingest.py --strategy section

EXPOSE 7860
CMD ["streamlit", "run", "frontend/app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true"]
