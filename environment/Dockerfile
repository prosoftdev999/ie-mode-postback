FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
WORKDIR /app
COPY data/ /evidence/
RUN chmod -R a-w /evidence \
    && mkdir -p /home/agent /app/output \
    && ln -s /evidence /app/data \
    && mkdir -p /logs/verifier /logs/artifacts \
    && chown -R 1000:1000 /home/agent /app/output /logs
ENV HOME=/home/agent
