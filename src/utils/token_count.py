import tiktoken

def count_tokens(text: str) -> int:
    """
    Count the number of tokens in the text using tiktoken
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))