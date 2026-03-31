# --- STAGE 1: Local Development ---
FROM node:20-alpine AS development
WORKDIR /app
# Install dependencies
COPY package*.json ./
RUN npm install
# Copy source code
COPY . .
# Start the Vite Dev Server
CMD ["npm", "run", "dev"]

# --- STAGE 2: Production Build ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- STAGE 3: Nginx Serving (Production Only) ---
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]