function filterRoutes() {
    const route = document.getElementById('route').value;
    filter = route.value.toLowerCase()
    div = document.getElementById('route-list')

    for (i = 0; i < a.length; i++) {
        txtValue = a[i].textContent || a[i].innerText;
        if (txtValue.toLowerCase().indexOf(filter) > -1) {
            a[i].style.display = "";
        } else {
            a[i].style.display = "none";
        }
    }
}