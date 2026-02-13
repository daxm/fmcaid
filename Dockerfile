FROM python:3.11-slim

WORKDIR /app

COPY fmcaid/ ./fmcaid/
COPY pyproject.toml README.md LICENSE ./

RUN pip install --no-cache-dir .

ENTRYPOINT ["python"]
CMD ["-m", "fmcaid"]
