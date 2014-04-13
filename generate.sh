# generate python code for the protobuff definition
is_module=orwell/messages/__init__.py
if [ ! -e "$is_module" ] ; then
	mkdir -p orwell/messages
	touch "$is_module"
fi
protoc -I=messages --python_out=orwell/messages/ messages/controller.proto
protoc -I=messages --python_out=orwell/messages/ messages/server-game.proto
protoc -I=messages --python_out=orwell/messages/ messages/server-web.proto
protoc -I=messages --python_out=orwell/messages/ messages/robot.proto
