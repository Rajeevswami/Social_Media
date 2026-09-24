# Minimal Redis for Render's private-service runtime.
FROM redis:7-alpine

CMD ["redis-server", "--save", "", "--appendonly", "no"]
