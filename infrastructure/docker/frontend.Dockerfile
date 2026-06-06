FROM node:20-slim

WORKDIR /app

# node_modules lives on the bind-mounted volume (installed by scripts/setup.sh).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
