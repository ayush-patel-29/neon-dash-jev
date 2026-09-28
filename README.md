# Neon Dash: You vs Jev

This project is a small browser game where a human races against an AI runner called Jev. The idea is simple: same track, same speed, same obstacle patterns, and the AI has to decide whether to jump or keep moving.

Jev is TypeSafe’s decision model. Instead of generating text, it evaluates structured state and returns a typed action that code can use immediately. In this app, the browser sends the next obstacle and runner state to the Python backend, the backend validates it, and then asks Jev for a decision. That decision is fed straight back into the game loop for the second runner.

## Implementation

The project is split between a lightweight frontend and a small Python API service.

- `index.html` handles the game visuals, input, canvas rendering, score tracking, and collision logic.
- `server.py` serves the app and exposes the decision endpoint.
- The browser sends obstacle state to `/api/decide`.
- The backend checks the payload and calls the TypeSafe client.
- Jev responds with an action such as `jump` or `run`.
- The response is used to control the AI runner in the race.

This keeps the game logic in the browser while the decision layer lives in the backend, which makes the project easy to demo and easy to extend.

## Setup

Install the dependencies and add your key to a `.env` file:

```env
TYPESAFE_API_KEY=your_key_here
```

Then start the app:

```bash
python server.py
```

Open the browser at:

```text
http://localhost:8000
```

## Notes

The game still runs without the key, but the AI runner will not be active until the environment is configured.
