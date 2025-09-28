
def getConvoResponse(convo: list):
    """
    takes in convo and streams the text response

    Parameters:
        convo (str): list of past messages
    Returns:
        res (str | dict): ai response or dict with shape { "top": [ {...}, {...} ], "jewelry": [ {...} ] }
    """
    history = build(convo)
    cfg = types.GenerateContentConfig()
    print(convo, history)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=history,
        config=cfg,
    ).text

    if response[:7] != "```json":
        return response
    else:
        return json.loads(response[8:-4])


def build(convo):
    """Build ai history from convo"""
    contents: list[types.Content] = []

    contents.append(types.Content(role="user", parts=[TYPES_CONVO_PROMPT]))
    # {"convo": [{"content": "Hi", "role": "user"}, {"content": "Hmm, I received an unexpected response format.", "role": "model"}, {"content": "H", "role": "user"}]F
    for message in convo:
        role = message["role"]
        content = message["content"]
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content)]))
    return contents
