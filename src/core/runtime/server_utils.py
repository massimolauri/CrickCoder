import os
from typing import List, Dict, Any

def normalize_path(project_path: str) -> str:
    return os.path.abspath(project_path.strip('"').strip("'"))

def transform_runs_to_messages(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trasforma una lista di runs Agno in una lista di ChatMessage per la UI.

    Ogni run rappresenta una esecuzione di un agente in risposta a un input utente.
    Struttura attesa di una run:
    - input: dict con input_content (messaggio utente)
    - events: lista di eventi (RunContent, ToolCallStarted, ToolCallCompleted)
    - content: contenuto testuale aggregato (opzionale)
    - agent_name: nome dell'agente
    - created_at: timestamp

    Ritorna lista di ChatMessage nel formato:
    - id: numero (timestamp)
    - role: 'user' o 'assistant'
    - content: string (per messaggi utente)
    - timeline: lista di TimelineItem (per messaggi assistant)
    """
    messages = []
    message_id_counter = 1  # Simple counter for IDs

    for run in runs:
        # 1. Crea messaggio utente dall'input
        input_data = run.get('input', {})
        user_content = None

        if isinstance(input_data, dict):
            user_content = input_data.get('input_content') or input_data.get('message')
        elif isinstance(input_data, str):
            user_content = input_data

        if user_content:
            user_message = {
                'id': message_id_counter,
                'role': 'user',
                'content': user_content
            }
            messages.append(user_message)
            message_id_counter += 1

        # 2. Crea messaggio assistant dagli eventi
        events = run.get('events', [])
        agent_name = run.get('agent_name', 'System')

        if events or run.get('content'):
            assistant_message = {
                'id': message_id_counter,
                'role': 'assistant',
                'timeline': []
            }
            message_id_counter += 1

            timeline = assistant_message['timeline']
            pending_tools = {}  # Mappa tool_name -> index nella timeline

            # Processa eventi in ordine
            for event in events:
                event_type = event.get('event', '') if isinstance(event, dict) else getattr(event, 'event', '')

                # RunContent -> text timeline item
                if event_type in ['RunContent', 'IntermediateRunContent']:
                    content = event.get('content', '')
                    if content:
                        # Cerca se c'è già un item text dello stesso agente
                        if timeline and timeline[-1]['type'] == 'text' and timeline[-1]['agent'] == agent_name:
                            # Appendi al contenuto esistente
                            timeline[-1]['content'] += content
                        else:
                            # Nuovo item text
                            timeline.append({
                                'type': 'text',
                                'content': content,
                                'agent': agent_name
                            })

                # ToolCallStarted -> tool timeline item con status running
                elif event_type == 'ToolCallStarted':
                    tool_data = event.get('tool', {})
                    if isinstance(tool_data, dict):
                        tool_name = tool_data.get('tool_name', 'unknown')
                        tool_args = tool_data.get('tool_args', {})
                    else:
                        tool_name = getattr(tool_data, 'tool_name', 'unknown')
                        tool_args = getattr(tool_data, 'tool_args', {})

                    tool_item = {
                        'type': 'tool',
                        'tool': tool_name,
                        'args': tool_args,
                        'status': 'running',
                        'agent': agent_name
                    }
                    timeline.append(tool_item)
                    pending_tools[tool_name] = len(timeline) - 1

                # ToolCallCompleted -> aggiorna tool a completed o converte in terminal
                elif event_type == 'ToolCallCompleted':
                    tool_data = event.get('tool', {})
                    if isinstance(tool_data, dict):
                        tool_name = tool_data.get('tool_name', 'unknown')
                        result = str(tool_data.get('result', ''))
                    else:
                        tool_name = getattr(tool_data, 'tool_name', 'unknown')
                        result = str(getattr(tool_data, 'result', ''))

                    # Cerca l'ultimo tool con questo nome nello stato running
                    tool_index = pending_tools.get(tool_name)
                    if tool_index is not None and tool_index < len(timeline):
                        tool_item = timeline[tool_index]
                        if tool_item['type'] == 'tool' and tool_item['status'] == 'running':
                            # Verifica se è un tool terminale (shell/build)
                            is_terminal = ('Exit Code' in result or
                                          'shell' in tool_name.lower() or
                                          'build' in tool_name.lower())

                            if is_terminal:
                                # Converti in terminal item
                                timeline[tool_index] = {
                                    'type': 'terminal',
                                    'command': tool_name,
                                    'output': result,
                                    'agent': agent_name
                                }
                            else:
                                # Aggiorna a completed
                                tool_item['status'] = 'completed'
                                timeline[tool_index] = tool_item

                            # Rimuovi dai pending
                            del pending_tools[tool_name]

            # Se non ci sono eventi ma c'è content, crea un item text dal content
            if not timeline and run.get('content'):
                timeline.append({
                    'type': 'text',
                    'content': run['content'],
                    'agent': agent_name
                })

            # Aggiungi il messaggio assistant solo se ha timeline
            if timeline:
                messages.append(assistant_message)

    return messages
