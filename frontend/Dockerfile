# Step 1: Build the React App
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies first
COPY package*.json ./
RUN npm install

# Copy the rest of the code
COPY . .

# Pull in the API URL from docker-compose.yml
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build the production files
RUN npm run build

# Step 2: Serve with Nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]