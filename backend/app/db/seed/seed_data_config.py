from dataclasses import dataclass


@dataclass
class SeedTestData:
    # Credentials
    admin_username: str = "admin"
    admin_password: str = "genadmin"
    supervisor_username: str = "supervisor1"
    supervisor_password: str = "gensupervisor1"
    operator_username: str = "operator1"
    operator_password: str = "genoperator1"

    # Database entry ids
    admin_user_id = "00000196-1b89-8e8e-905c-0eefdb9008f1"
    operator_id: str = "00000196-02d3-603c-994a-b616f314b0ba"
    operator_user_id: str = "00000196-a5a9-9988-b801-88d1fac6782c"
    zen_operator_id: str = "8c34409c-2599-45a4-b709-3f9787c19e94"
    zen_operator_user_id: str = "00000196-1b89-8e8e-905c-0eefdb9008f1"
    data_source_id: str = "00000196-10bb-37d8-8cba-1712b4991f2d"
    llm_analyst_speaker_separator_id: str = "00000196-02d3-6032-82f1-a5fca4a356ab"
    llm_analyst_kpi_analyzer_id: str = "00000196-3d9e-4b48-ab7f-f62281c1d634"
    llm_analyst_in_progress_hostility_id: str = "00000196-3daa-544d-baee-2d0bb52aefae"
    llm_provider_id: str = "00000196-19d2-9c28-a2dd-561fff608fa0"
    local_llm_provider_id: str = "00000196-19d2-9c28-a2dd-562fff608fa0"
    local_llm_provider_llama_id: str = "00000196-19d2-9c28-a2dd-563fff608fa0"
    local_llm_provider_gpt_oss_id: str = "00000196-19d2-9c28-a2dd-564fff608fa0"
    local_llm_provider_vllm_llama: str = "00000196-19d2-9c28-a2dd-565fff608fa0"
    default_agent_id: str = "00000196-a688-fd6f-af6d-8dc6c281d697"

    transcribe_operator_id: str = "90f1e6dd-fde0-4970-a83a-31ca7f84ab45"
    transcribe_operator_user_id: str = "31a1e5ed-2f1d-485d-bb45-b6c9f4282b4f"
    transcribe_data_source_id: str = "5223b67f-4e86-494d-8ae5-f709d05c3e27"

    genassist_agent_id: str = "00000195-10bb-37d7-8cba-1712b4990001"

    # Prompts
    speaker_separation_llm_analyst_prompt = """You are an AI assistant that processes transcribed customer service conversations that 
        contains a list of objects as a dict where each one has these fields:
                            - "text": The spoken sentence.
                            - "start_time": The start time of that part of the conversation.
                            - "end_time": The end time of that part of the conversation.
        
                            Your task is to take the items and separate them into an array of JSON objects where 
                            based on context you assign if the speaker is the agent or the customer.
                            Each object should have:
                            - "text": The spoken sentence.
                            - "speaker": Either "Customer" or "Agent".
                            - "start_time": The start time of that part of the conversation.
                            - "end_time": The end time of that part of the conversation.
                            
                            If the speaker doesn't change for two consecutive objects, they should be in one object.
                            If from context it is evident that there is are wrong words in the transcription you are 
                            allowed to modify them.
                            
                            Ensure the response is a **valid JSON array**, not inside Markdown backticks.
                            
                            Example:
                            [
                              {
                                "text": "Hello, how can I help you today?",
                                "speaker": "Agent",
                                "start_time": 0.0,
                                "end_time": 2.5,
                              },
                              {
                                "text": "I have an issue with my bill.",
                                "speaker": "Customer",
                                "start_time": 15.0
                                "end_time": 20,
                              }
                            ]
                            """
    kpi_analyzer_system_prompt = """You are a helpful customer experience expert."""
    in_progress_hostility_system_prompt = (
        """"You are a helpful but critical call center conversation analyst."""
    )
    default_agent_prompt = """You are a helpful support assistant for our product. Your role is to:
 1. Answer customer questions about our product features and capabilities
 2. Provide technical support and troubleshooting guidance
 3. Help users understand system requirements and integration options
 4. Use the knowledge base to provide accurate information
 5. Use available tools to assist with tasks like currency conversion when needed

 Always be professional, clear, and concise in your responses. If you don't know something, say so and offer to help find the information."""


seed_test_data = SeedTestData()
