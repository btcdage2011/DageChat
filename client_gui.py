import json
from client_persistent import PersistentChatUser

class GuiChatUser(PersistentChatUser):

    def __init__(self, db_filename, on_message_callback=None, nickname=None):
        self.ui_callback = on_message_callback
        super().__init__(db_filename, nickname=nickname)

    def _print_to_ui(self, msg_type, data):
        if self.ui_callback:
            self.ui_callback(msg_type, data)
        else:
            print(f'[{msg_type}] {data}')

    def _handle_metadata(self, event):
        super()._handle_metadata(event)
        self._print_to_ui('contact_update', {'pubkey': event['pubkey']})

    def _handle_deletion(self, event):
        super()._handle_deletion(event)
        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
        if target_ids:
            self._print_to_ui('delete', {'ids': target_ids})