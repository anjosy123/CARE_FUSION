from django.utils.deprecation import MiddlewareMixin

class NoCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Default no-cache headers for all responses
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        # Special condition to prevent caching for the logout response
        if request.path == '/logout/':
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        
        return response

