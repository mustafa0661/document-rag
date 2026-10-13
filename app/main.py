
from ollama import Client

MODEL_NAME = "qwen3:4b-instruct"

def main():
    client = Client(host="http://localhost:11434")

    response = client.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "Türkçe ve kısa cevaplar veren bir asistansın."
            },
            {
                "role": "user",
                "content": "RAG mimarisini iki cümleyle açıkla."
            }
        ],
        options={
            "temperature": 0.1,
            "num_ctx": 4096
        }
    )

    print(response.message.content)


if __name__ == "__main__":
    main()
