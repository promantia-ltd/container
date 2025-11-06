frappe.after_ajax(() => {
    // Function to apply Enter key navigation
    function enableEnterNavigation($wrapper) {
        function handleEnterKey(fieldname) {
            return function (e) {
                if (e.keyCode === 13) {
                    e.preventDefault();
                    e.stopPropagation();

                    let $current = $(this);
                    let currentValue = $current.val();

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
                            $current.blur();
                        }
                    }, 100);

                    return false;
                }
            };
        }

        $wrapper.off('keydown.global_enter');
        $wrapper.on('keydown.global_enter', 'input[data-fieldname]', function (e) {
            let fieldname = $(this).attr('data-fieldname');
            handleEnterKey(fieldname).call(this, e);
        });
    }

    const observer = new MutationObserver(() => {
        $('.modal.in, .frappe-control[data-fieldtype="Table"] .grid-body').each(function () {
            enableEnterNavigation($(this));
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
});
