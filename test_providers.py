"""Test provider selection for the active window."""

from src.mcp_desktop_visual.providers.registry import get_registry
from src.mcp_desktop_visual.windows import get_active_window_info

def main():
    # Initialize registry
    registry = get_registry()
    
    # Get active window
    info = get_active_window_info()
    if not info:
        print("No active window found")
        return
    
    print(f"Janela ativa: {info['title']}")
    print(f"Processo: {info['process_name']}")
    print(f"Classe: {info['class_name']}")
    print()
    
    # Find best provider
    provider = registry.get_provider(
        info['process_name'],
        info['title'],
        info['class_name']
    )
    
    if provider:
        print(f"Provider escolhido: {provider.name} (prioridade {provider.priority})")
        print(f"Disponível: {provider.is_available()}")
        
        # Try detection
        if provider.is_available():
            print("\nTestando detecção...")
            result = provider.detect(window_handle=info['handle'])
            print(f"Sucesso: {result.success}")
            print(f"Elementos detectados: {len(result.elements)}")
            print(f"Tempo: {result.detection_time_ms:.1f}ms")
            
            if result.elements:
                print("\nPrimeiros 10 elementos:")
                for elem in result.elements[:10]:
                    text = elem.text or elem.label or "(sem texto)"
                    print(f"  - {elem.type.value}: {text[:50]}")
    else:
        print("Nenhum provider disponível - usando OCR como fallback")

if __name__ == "__main__":
    main()
