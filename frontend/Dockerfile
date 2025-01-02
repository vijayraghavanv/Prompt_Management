FROM node:20-slim

WORKDIR /app

# Install git
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Clone frontend repository
RUN git clone https://github.com/vijayraghavanv/YAPMT.git .

# Install dependencies
RUN npm install

# Build the application
RUN npm run build

# Run the application in development mode
CMD ["npm", "run", "dev"]