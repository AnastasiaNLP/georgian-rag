import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from core.clients import get_qdrant_client
from config.settings import settings
from pipeline.rag import EnhancedGeorgianRAG

async def test_conversation_memory():
    """test conversation manager memory"""
    # initialize rag
    api_keys = {
        'anthropic_api_key': settings.claude.api_key,
        'groq_api_key': settings.groq.api_key,
        'upstash_url': os.getenv('UPSTASH_REDIS_URL', ''),
        'upstash_token': os.getenv('UPSTASH_REDIS_TOKEN', ''),
    }

    rag_config = {
        'collection_name': settings.qdrant.collection_name,
        'embedding_model': settings.embedding.model_name
    }

    qdrant_client = get_qdrant_client()

    from search.HybridSearchEngine import HybridSearchEngine
    from utils.disclaimer import DisclaimerManager

    hybrid_search = HybridSearchEngine(
        qdrant_client=qdrant_client,
        collection_name=rag_config['collection_name'],
        embedding_model=rag_config['embedding_model']
    )

    disclaimer_manager = DisclaimerManager()

    rag = EnhancedGeorgianRAG(
        qdrant_system=None,
        hybrid_search_integrator=hybrid_search,
        disclaimer_manager=disclaimer_manager,
        api_keys=api_keys,
        config=rag_config
    )

    await rag.initialize()

    print("\nTesting conversation memory")

    # test 1: first query (no conversation)
    print("\nTest 1: First query (no context)")
    result1 = await rag.answer_question(
        query="What are the best places in Tbilisi?",
        target_language="en",
        top_k=3
    )
    print(f"Response length: {len(result1['response'])} chars")

    # check if conversation manager exists
    if hasattr(rag, 'conversation_manager'):
        print(f"Conversationmanager found!")
        stats = rag.conversation_manager.get_stats()
        print(f"Stats: {stats}")

        # test 2: create conversation and add history
        print("\nTest 2: Testing conversation history")
        conv_id = "test_conv_123"

        # add first message
        rag.conversation_manager.add_message(
            conversation_id=conv_id,
            role="user",
            content="Tell me about Tbilisi",
            metadata={"language": "en"}
        )

        rag.conversation_manager.add_message(
            conversation_id=conv_id,
            role="assistant",
            content="Tbilisi is the capital of Georgia...",
            metadata={"language": "en"}
        )

        # get history
        history = rag.conversation_manager.get_history(conv_id)
        print(f"History contains {len(history)} messages")

        # get context window
        context = rag.conversation_manager.get_context_window(conv_id)
        print(f"Context window: {len(context)} chars")

        # test 3: check metadata
        metadata = rag.conversation_manager.get_conversation_metadata(conv_id)
        print(f"Metadata: {metadata}")

        # clean up
        rag.conversation_manager.clear_conversation(conv_id)
        print(f"Conversation cleared")
    else:
        print("Conversationmanager not found in rag!")

    print("\nTest complete!")

if __name__ == "__main__":
    asyncio.run(test_conversation_memory())