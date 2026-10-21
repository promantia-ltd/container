// Global desk customisation (loaded on every page via app_include_js):
// pressing Enter in a child-table grid input (or any input inside an open
// modal) commits the value and moves focus to the same field in the next row.
frappe.after_ajax(() => {
    // Bind the delegated Enter-key handler on one grid body / modal wrapper.
    function enableEnterNavigation($wrapper) {
        function handleEnterKey(fieldname) {
            return function (e) {
                if (e.keyCode === 13) {
                    e.preventDefault();
                    e.stopPropagation();

                    let $current = $(this);

                    // Commit the typed value before moving away from the cell.
                    $current.trigger('input').trigger('change');

                    let $currentRow = $current.closest('[data-idx]');
                    let currentRowIdx = $currentRow.attr('data-idx');

                    setTimeout(() => {
                        let nextRowIdx = parseInt(currentRowIdx) + 1;
                        let $nextRow = $wrapper.find('[data-idx="' + nextRowIdx + '"]');

                        if ($nextRow.length > 0) {
                            let $nextInput = $nextRow.find('input[data-fieldname="' + fieldname + '"]');
                            if ($nextInput.length > 0 && $nextInput.is(':visible')) {
                                $nextInput.focus().select();
                            } else {
                                let $nextCell = $nextRow.find('.grid-static-col[data-fieldname="' + fieldname + '"]');
                                // Input not rendered yet: click the static cell to make the grid
                                // render its editable input, then focus it once it exists.
                                if ($nextCell.length > 0) {
                                    $nextCell.click();
                                    setTimeout(() => {
                                        $nextInput = $nextRow.find('input[data-fieldname="' + fieldname + '"]');
                                        if ($nextInput.length > 0) {
                                            $nextInput.focus().select();
                                        }
                                    }, 150);
                                }
                            }
                        } else {
                            // Last row: just leave the field.
                            $current.blur();
                        }
                    }, 100);

                    return false;
                }
            };
        }

        // Namespaced off/on so repeated calls from the observer don't stack handlers.
        $wrapper.off('keydown.global_enter');
        $wrapper.on('keydown.global_enter', 'input[data-fieldname]', function (e) {
            let fieldname = $(this).attr('data-fieldname');
            handleEnterKey(fieldname).call(this, e);
        });
    }

    // Grids and dialogs are rendered dynamically, so re-bind on every DOM change.
    const observer = new MutationObserver(() => {
        $('.modal.in, .frappe-control[data-fieldtype="Table"] .grid-body').each(function () {
            enableEnterNavigation($(this));
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
});
