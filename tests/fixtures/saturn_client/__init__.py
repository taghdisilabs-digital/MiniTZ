class SaturnConnection:
    def list_resources(self):
        return [{"name": "test-l40s-resource"}]

    def list_options(self, option_type):
        return [{"name": "L40S"}]
