// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview


client<llm> ImageClient {
  provider "google-ai"
  options {
    model "gemini-2.0-flash"
    // api_key defaults to env.OPENAI_API_KEY
  }
}


client<llm> TextClient {
  provider "google-ai"
  options {
    model "gemini-2.0-flash"
    // api_key defaults to env.OPENAI_API_KEY
  }
}

client<llm> TestClient {
  provider "google-ai"
  options {
    model "gemini-2.0-flash"
    generationConfig {
      temperature 0.0
    }
  }

}
