
function change_form(val,val_list,prefix) {
    $('label[for^="'+prefix+'"]').hide();
    $('input[id^='+prefix+']').hide();
    $.each( val_list[val], function( key, value ) {
        $('#'+value).removeAttr('hidden').show();
        $('label[for="'+value+'"]').show();
    });

}
