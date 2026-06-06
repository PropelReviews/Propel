FROM node:20-slim

WORKDIR /app

# Placeholder until Vite app is scaffolded.
# Keeps the container running so docker-compose up succeeds.
CMD ["node", "-e", "console.log('Propel frontend placeholder — waiting for app code'); setInterval(() => {}, 3600000)"]
