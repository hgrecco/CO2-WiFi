window.onload = function(){
  setTimeout(function() {
    document.getElementById("app-content").classList.remove("my-hide");
    document.getElementById("div-loading-spinner").classList.add("my-hide");
    // var iso = new Isotope('.grid', {
    //   // options
    //   itemSelector: '.grid-item',
    //   layoutMode: 'fitRows'
    // });
    //
    // document.iso = iso;
    // var checkboxes = document.querySelectorAll('#filter-buildings input[type="checkbox"]');
    // for (var i = 0; i < checkboxes.length; i++) {
    //   checkboxes[i].checked = true;
    // }
  }, 2000);
}