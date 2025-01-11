import json


def get_claude_timetable_response(bedrock_runtime, prompt, image_data, mimetype):
    timetable_structure = {
        "Monday": [
            {
                "start_time": "The start time of the class. (e.g. 09:00)",
                "end_time": "The end time of the class. (e.g. 10:00)",
                "name": "The name of the class. (e.g. Introduction to Computer Science)",
                "index": "The index of the class. (e.g. 1)"
            }
        ],
        "Tuesday": [],
        "Wednesday": [],
        "Thursday": [],
        "Friday": []
    }

    timetable_example = {
      "Monday": [
        {
          "start_time": "11:00",
          "end_time": "12:00",
          "name": "사회물리학: 네트워크적 접근",
          "index": 1
        },
        {
          "start_time": "13:00",
          "end_time": "15:00",
          "name": "AI 원리 및 최신기술",
          "index": 2
        },
      ],
      "Tuesday": [
        {
          "start_time": "09:00",
          "end_time": "12:00",
          "name": "확장현실 프로젝트",
          "index": 1
        }
      ],
      "Wednesday": [],
      "Thursday": [
        {
          "start_time": "11:00",
          "end_time": "12:00",
          "name": "사회물리학: 네트워크적 접근",
          "index": 1
        },
        {
          "start_time": "13:00",
          "end_time": "14:00",
          "name": "다변수해석학과 응용",
          "index": 2
        },
        {
          "start_time": "16:00",
          "end_time": "17:00",
          "name": "프로그래밍 언어 및 컴파일러",
          "index": 3
        }
      ],
      "Friday": []
    }

    system_prompt = f'''You are a time table manager for a school club. Users will give you their timetables in various formats, not limited to text and images. Analyze the message and extract the timetable information. Respond with the extracted information in the following structured format:

    # Format
    {json.dumps(timetable_structure)}

    # Example
    {json.dumps(timetable_example)}

    # Note
    - If the given information is not enough to extract the timetable. Do not ask for additional information.
    '''


    prompt = prompt if prompt else "empty"

    try:
        content = []

        if image_data:
            content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mimetype,
                                "data": image_data
                            }
                        })
        
        content.append({
            "type": "text",
            "text": prompt
        })

        # Bedrock 요청 바디 구성
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "temperature": 0.7
        })
        
        # Bedrock API 호출
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            contentType='application/json',
            body=body
        )
        
        # 응답 파싱
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        print(f"Bedrock API 에러: {str(e)}")
        return "죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."