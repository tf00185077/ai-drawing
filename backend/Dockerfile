FROM python:3.11-slim

WORKDIR /workspace/backend

COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt

COPY backend /workspace/backend
COPY style_presets /workspace/style_presets
COPY prompt_library /opt/ai-drawing-seed/prompt_library

ENV PYTHONUNBUFFERED=1
ENV DATA_ROOT=/data
ENV PROMPT_LIBRARY_SEED_DIR=/opt/ai-drawing-seed/prompt_library

ENTRYPOINT ["python", "scripts/docker_entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
