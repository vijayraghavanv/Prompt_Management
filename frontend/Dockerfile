FROM node:22-slim

WORKDIR /app
COPY .env .env
# Install git
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Clone repository
RUN git clone https://github.com/vijayraghavanv/YAPMT.git .

# Install all dependencies
RUN npm install --legacy-peer-deps

# Build the application
RUN npm run build

# Run the application in production mode
CMD ["npm", "run", "start"]