$('#forward').on('mousedown', function(){

$.get('/forward');
});

$('#forward').on('mouseup', function(){

$.get('/stop');
});

$('#backward').on('mousedown', function(){

$.get('/backward');
});

$('#backward').on('mouseup', function(){

$.get('/stop');
});

$('#left').on('mousedown', function(){

$.get('/left');
});

$('#left').on('mouseup', function(){

$.get('/stop');
});

$('#right').on('mousedown', function(){

$.get('/right');
});

$('#right').on('mouseup', function(){

$.get('/stop');
});