docker build -t backster .
docker run --env-file .env -p 8000:8000 backster
docker tag backster f23e6b34486d49dcacf5687a00e96bc0.azurecr.io/backster:latest
az acr login --name f23e6b34486d49dcacf5687a00e96bc0
docker push f23e6b34486d49dcacf5687a00e96bc0.azurecr.io/backster:latest