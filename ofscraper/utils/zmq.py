# # import zmq
# # number=10

# def get_zmq_receiver(port):
#     context = zmq.Context()
#     socket = context.socket(zmq.PULL)
#     socket.connect(f"tcp://localhost:{port}")
#     return socket


# def get_zmq_sender(port):
#     context = zmq.Context()
#     socket = context.socket(zmq.PUSH)
#     socket.bind(f"tcp://localhost:{port}")
#     return socket
